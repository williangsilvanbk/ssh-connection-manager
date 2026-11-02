#!/usr/bin/env python3
"""
Gerenciador local de conexoes SSH para Linux (Ubuntu Desktop).
Uso:
ssh-menu.py                 No terminal: lista e pede o servidor.
ssh-menu.py open <ref>      Abre o servidor em uma nova aba do Terminal.
ssh-menu.py run <nome>      Conecta no terminal atual (sem abrir aba).
ssh-menu.py list            Lista os servidores do inventario.
ssh-menu.py ui              Abre o formulario no navegador.
ssh-menu.py indicator       Inicia o menu na barra de tarefas.
"""
import json
import os
import re
import secrets
import shlex
import socket
import subprocess
import sys
import threading
import time
import platform
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

CONFIG = os.path.expanduser("~/.config/ssh-menu/servers.json")
SELF = os.path.realpath(__file__)
IS_MAC = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"

DEFAULT = {
    "groups": [
        {
            "name": "Producao",
            "servers": [
                {"name": "servidor-01", "host": "10.0.0.10", "user": "ubuntu"}
            ],
        },
        {
            "name": "AWS (exemplo, edite)",
            "servers": [
                {
                    "name": "exemplo-ec2",
                    "host": "10.0.0.10",
                    "user": "ec2-user",
                    "key": "~/.ssh/minha-chave.pem",
                }
            ],
        },
        {
            "name": "ASA / ScaleFT (exemplo, edite)",
            "servers": [
                {"name": "exemplo-asa", "type": "sft", "host": "nome-do-servidor"}
            ],
        },
    ]
}

def ensure_inventory():
    if not os.path.exists(CONFIG):
        os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(DEFAULT, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.chmod(CONFIG, 0o600)

def load():
    try:
        ensure_inventory()
        with open(CONFIG, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data.get("groups"), list):
            return None, "o arquivo precisa ter a chave 'groups' (lista)"
        for g in data["groups"]:
            for s in g.get("servers", []):
                if "name" not in s or "host" not in s:
                    return None, "todo servidor precisa de 'name' e 'host'"
        return data, None
    except (OSError, ValueError) as e:
        return None, str(e)

def clean(text):
    return str(text).replace("|", "/").replace("\n", " ")

def build_cmd(s):
    host = s["host"]
    if s.get("type", "ssh") == "sft":
        return ["sft", "ssh", host]
    cmd = ["ssh"]
    key = s.get("key")
    if key:
        cmd += ["-i", os.path.expanduser(key), "-o", "IdentitiesOnly=yes"]
    port = int(s.get("port", 22))
    if port != 22:
        cmd += ["-p", str(port)]
    user = s.get("user")
    cmd.append("%s@%s" % (user, host) if user else host)
    return cmd

def check_key(s):
    key = s.get("key")
    if s.get("type", "ssh") == "sft" or not key:
        return None
    path = os.path.expanduser(key)
    try:
        if not os.path.isfile(path):
            return "Chave nao encontrada: %s" % path
        if os.stat(path).st_mode & 0o077:
            return "Permissao da chave muito aberta. Rode: chmod 400 %s" % shlex.quote(path)
    except OSError as e:
        return "Sem acesso a chave (%s)." % e
    return None

def notify(msg):
    if IS_LINUX:
        try:
            subprocess.run(["notify-send", "SSH Menu", msg], check=False, capture_output=True)
        except FileNotFoundError:
            print(msg)
    elif IS_MAC:
        esc = msg.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.run(["osascript", "-e", 'display notification "%s" with title "SSH Menu"' % esc], check=False)

def detect_terminal():
    terminals = [
        ("gnome-terminal", ["gnome-terminal", "--tab", "--title", "SSH", "--", "bash", "-c"]),
        ("konsole", ["konsole", "--new-tab", "-e"]),
        ("xfce4-terminal", ["xfce4-terminal", "--tab", "-e"]),
        ("mate-terminal", ["mate-terminal", "--tab", "-e"]),
        ("terminator", ["terminator", "--new-tab", "-e"]),
        ("tilix", ["tilix", "--new-tab", "-e"]),
    ]
    for name, cmd_prefix in terminals:
        try:
            result = subprocess.run(["which", name], capture_output=True, check=False)
            if result.returncode == 0:
                return name, cmd_prefix
        except Exception:
            continue
    return None, None

def flat(data):
    return [(g.get("name", "Sem grupo"), s) for g in data["groups"] for s in g.get("servers", [])]

def find(data, ref):
    if ":" in ref:
        a, _, b = ref.partition(":")
        if a.isdigit() and b.isdigit():
            try:
                return data["groups"][int(a)]["servers"][int(b)]
            except (IndexError, KeyError):
                return None
    for _, s in flat(data):
        if s["name"].lower() == ref.lower():
            return s
    return None

def open_in_terminal(ref):
    data, err = load()
    if err:
        notify("Erro no inventario: %s" % err)
        return
    s = find(data, ref)
    if not s:
        notify("Servidor nao encontrado: %s" % ref)
        return
    problem = check_key(s)
    if problem:
        notify(problem)
        return
    
    line = " ".join(shlex.quote(x) for x in build_cmd(s))
    
    if IS_MAC:
        esc = lambda t: t.replace("\\", "\\\\").replace('"', '\\"')
        script = ['tell application "Terminal"', "activate", 'set t to do script "%s"' % esc(line), 'set custom title of t to "%s"' % esc(s["name"]), "end tell"]
        args = ["osascript"]
        for ln in script:
            args += ["-e", ln]
        subprocess.run(args, check=False)
    elif IS_LINUX:
        term_name, cmd_prefix = detect_terminal()
        if not term_name:
            notify("Nenhum terminal suportado encontrado. Use 'run' no terminal.")
            return
        cmd = cmd_prefix + [line + "; exec bash"]
        try:
            subprocess.Popen(cmd, start_new_session=True)
        except Exception as e:
            notify("Erro ao abrir terminal: %s" % e)

def run_here(ref):
    data, err = load()
    if err:
        sys.exit("Erro no inventario: %s" % err)
    s = find(data, ref)
    if not s:
        sys.exit("Servidor nao encontrado: %s" % ref)
    problem = check_key(s)
    if problem:
        sys.exit(problem)
    cmd = build_cmd(s)
    os.execvp(cmd[0], cmd)

def pick():
    data, err = load()
    if err:
        sys.exit("Erro no inventario: %s" % err)
    items = flat(data)
    if not items:
        sys.exit("Inventario vazio: edite %s" % CONFIG)
    for i, (g, s) in enumerate(items, 1):
        who = "%s@%s" % (s["user"], s["host"]) if s.get("user") else s["host"]
        print("%3d) [%s] %s  (%s)" % (i, g, s["name"], who))
    sel = input("\nNumero ou parte do nome: ").strip()
    if sel.isdigit() and 1 <= int(sel) <= len(items):
        s = items[int(sel) - 1][1]
    else:
        matches = [x[1] for x in items if sel.lower() in x[1]["name"].lower()]
        if len(matches) != 1:
            sys.exit("%d resultados para '%s'. Seja mais especifico." % (len(matches), sel))
        s = matches[0]
    problem = check_key(s)
    if problem:
        sys.exit(problem)
    cmd = build_cmd(s)
    print("\n> " + " ".join(shlex.quote(x) for x in cmd) + "\n")
    os.execvp(cmd[0], cmd)

# ---------------------------------------------------------------------------
# Formulario web local (ssh-menu.py ui)
# ---------------------------------------------------------------------------
IDLE_SECONDS = 15 * 60
KEY_DIRS = ["~/.ssh", "~/Documents/Chaves AWS-Virtualization", "~/keys", "~/aws-keys"]
NAME_RE = re.compile(r"^[^\x00-\x1f]{1,60}$")
HOST_RE = re.compile(r"^[A-Za-z0-9._:-]{1,255}$")
USER_RE = re.compile(r"^[A-Za-z0-9._@-]{1,64}$")
WRITE_LOCK = threading.Lock()

PAGE = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SSH Menu - Servidores</title>
<style>
:root{--bg:#f4f5f8;--card:#fff;--text:#1c2230;--muted:#5b6579;--line:#dbe0ea;--accent:#2a56e8;--accent-text:#fff;--danger:#b8332a;--ok:#1b7f48;--warn:#9a5b00;--chip:#eef1f8}
@media (prefers-color-scheme:dark){:root{--bg:#12151b;--card:#1b2029;--text:#e7eaf1;--muted:#9aa3b5;--line:#2b3340;--accent:#7b9cff;--accent-text:#0d1220;--danger:#ff7f70;--ok:#4fc58b;--warn:#e3ac52;--chip:#242b37}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Ubuntu,Cantarell,"Helvetica Neue",sans-serif}
header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 24px;border-bottom:1px solid var(--line);background:var(--card)}
h1{font-size:18px;margin:0}
.sub{color:var(--muted);font-size:13px;margin-top:2px}
main{display:grid;grid-template-columns:minmax(300px,380px) 1fr;gap:20px;padding:20px 24px;max-width:1200px;margin:0 auto}
@media (max-width:820px){main{grid-template-columns:1fr;padding:16px}}
section{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px}
h2{font-size:15px;margin:0 0 12px}
label{display:block;font-size:13px;color:var(--muted);margin:12px 0 4px}
input[type=text],input[type=number],select{width:100%;padding:9px 10px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--text);font:inherit}
input:focus,select:focus,button:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.row{display:grid;grid-template-columns:1fr 90px;gap:10px}
fieldset{border:1px solid var(--line);border-radius:8px;margin:14px 0 0;padding:6px 12px 10px}
legend{font-size:13px;color:var(--muted);padding:0 6px}
.radio{display:flex;gap:8px;align-items:flex-start;margin:8px 0}
.radio input{margin-top:3px}
.radio small{display:block;color:var(--muted)}
button{font:inherit;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--text);padding:8px 14px;cursor:pointer}
button.primary{background:var(--accent);color:var(--accent-text);border-color:var(--accent);font-weight:600}
button.danger{color:var(--danger)}
button.small{padding:4px 10px;font-size:13px}
.actions{display:flex;gap:10px;margin-top:16px;flex-wrap:wrap}
.msg{margin-top:12px;font-size:13px;min-height:18px}
.msg.ok{color:var(--ok)}.msg.err{color:var(--danger)}.msg.warn{color:var(--warn)}
h3{font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:18px 0 6px}
h3:first-of-type{margin-top:0}
table{width:100%;border-collapse:collapse}
td{padding:8px 6px;border-top:1px solid var(--line);vertical-align:middle}
td.n{font-weight:600}
td.h{color:var(--muted);font-size:13px;word-break:break-all}
td.a{text-align:right;white-space:nowrap}
.chip{display:inline-block;padding:1px 8px;border-radius:99px;background:var(--chip);font-size:12px;color:var(--muted)}
.empty{color:var(--muted)}
.note{font-size:12px;color:var(--muted);margin-top:14px}
</style>
</head>
<body>
<header>
<div><h1>SSH Menu</h1><div class="sub" id="where"></div></div>
<button id="quit">Fechar formulario</button>
</header>
<main>
<section aria-labelledby="ft">
<h2 id="ft">Novo servidor</h2>
<form id="f" autocomplete="off">
<label for="grupo">Grupo</label>
<input type="text" id="grupo" list="grupos" placeholder="Ex.: AWS, Producao" required>
<datalist id="grupos"></datalist>
<label for="nome">Nome</label>
<input type="text" id="nome" placeholder="Ex.: servidor-01" maxlength="60" required>
<div class="row">
<div><label for="host">IP ou hostname</label><input type="text" id="host" placeholder="10.0.0.10" required></div>
<div><label for="porta">Porta</label><input type="number" id="porta" value="22" min="1" max="65535"></div>
</div>
<label for="usuario">Usuario</label>
<input type="text" id="usuario" placeholder="ubuntu, ec2-user, root...">
<fieldset>
<legend>Como autenticar</legend>
<div class="radio"><input type="radio" name="auth" id="a-key" value="key" checked><label for="a-key" style="margin:0;color:inherit">Chave (.pem)<small>Recomendado. O caminho da chave fica salvo, o conteudo nao.</small></label></div>
<div class="radio"><input type="radio" name="auth" id="a-pw" value="password"><label for="a-pw" style="margin:0;color:inherit">Senha<small>A senha nao e salva. O terminal pergunta a cada conexao.</small></label></div>
<div class="radio"><input type="radio" name="auth" id="a-sft" value="sft"><label for="a-sft" style="margin:0;color:inherit">ASA / ScaleFT (sft)<small>Usa "sft ssh nome-do-servidor". Informe o nome no campo IP ou hostname.</small></label></div>
</fieldset>
<div id="keybox">
<label for="keysel">Chave encontrada na maquina</label>
<select id="keysel"><option value="">Selecione...</option></select>
<label for="keypath">Ou digite o caminho do .pem</label>
<input type="text" id="keypath" placeholder="~/.ssh/minha-chave.pem">
<div class="msg" id="keyinfo"></div>
</div>
<div class="actions">
<button type="submit" class="primary" id="save">Salvar servidor</button>
<button type="button" id="test">Testar porta</button>
<button type="button" id="cancel" hidden>Cancelar edicao</button>
</div>
<div class="msg" id="msg" role="status" aria-live="polite"></div>
</form>
<p class="note">Nenhuma senha e gravada. Cada alteracao cria uma copia de seguranca em servers.json.bak.</p>
</section>
<section aria-labelledby="lt">
<h2 id="lt">Servidores cadastrados</h2>
<div id="list"></div>
</section>
</main>
<script>
const T = new URLSearchParams(location.search).get("t");
const $ = (id) => document.getElementById(id);
let state = {groups: [], keys: [], config: ""};
let editing = null;
async function api(path, opts) {
opts = opts || {};
const r = await fetch(path, {method: opts.method || "GET", headers: {"X-Token": T, "Content-Type": "application/json"}, body: opts.body ? JSON.stringify(opts.body) : undefined});
let j = {};
try { j = await r.json(); } catch (e) {}
if (!r.ok) throw new Error(j.error || ("Erro " + r.status));
return j;
}
function say(text, kind) { const m = $("msg"); m.textContent = text || ""; m.className = "msg " + (kind || ""); }
function authOf(s) { return s.type === "sft" ? "sft" : (s.key ? "key" : "password"); }
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
function render() {
$("where").textContent = "Inventario: " + state.config;
const dl = $("grupos"); dl.textContent = "";
state.groups.forEach((g) => { const o = document.createElement("option"); o.value = g.name; dl.appendChild(o); });
const ks = $("keysel"); const cur = ks.value; ks.textContent = "";
const first = document.createElement("option"); first.value = ""; first.textContent = state.keys.length ? "Selecione..." : "Nenhuma chave encontrada nas pastas padrao"; ks.appendChild(first);
state.keys.forEach((k) => { const o = document.createElement("option"); o.value = k.path; o.textContent = k.path + (k.ok ? "" : "  (permissao aberta)"); ks.appendChild(o); });
ks.value = cur;
const box = $("list"); box.textContent = "";
let total = 0;
state.groups.forEach((g, gi) => {
if (!g.servers || !g.servers.length) return;
box.appendChild(el("h3", "", g.name));
const t = document.createElement("table");
g.servers.forEach((s, si) => {
total++;
const tr = document.createElement("tr");
tr.appendChild(el("td", "n", s.name));
const dest = (s.user ? s.user + "@" : "") + s.host + (s.port && s.port !== 22 ? ":" + s.port : "");
tr.appendChild(el("td", "h", dest));
const tdc = document.createElement("td");
tdc.appendChild(el("span", "chip", {key: "chave", password: "senha", sft: "ASA"}[authOf(s)]));
tr.appendChild(tdc);
const ta = el("td", "a");
const be = el("button", "small", "Editar"); be.type = "button"; be.onclick = () => startEdit(gi, si);
const bt = el("button", "small", "Testar"); bt.type = "button"; bt.onclick = () => ping(s.host, s.port || 22, s.type === "sft");
const bd = el("button", "small danger", "Excluir"); bd.type = "button"; bd.onclick = () => del(gi, si, s.name);
ta.append(be, " ", bt, " ", bd);
tr.appendChild(ta);
t.appendChild(tr);
});
box.appendChild(t);
});
if (!total) box.appendChild(el("p", "empty", "Nenhum servidor cadastrado ainda."));
}
function updateAuth() {
const a = document.querySelector("input[name=auth]:checked").value;
$("keybox").hidden = a !== "key";
$("usuario").disabled = a === "sft";
$("porta").disabled = a === "sft";
$("test").disabled = a === "sft";
}
document.querySelectorAll("input[name=auth]").forEach((r) => r.addEventListener("change", updateAuth));
$("keysel").addEventListener("change", () => { if ($("keysel").value) { $("keypath").value = $("keysel").value; showKey(); } });
$("keypath").addEventListener("input", showKey);
function showKey() {
const p = $("keypath").value.trim(); const k = state.keys.find((x) => x.path === p);
const i = $("keyinfo");
if (!p) { i.textContent = ""; i.className = "msg"; return; }
if (!k) { i.textContent = "Caminho digitado a mao. A existencia e a permissao serao verificadas ao salvar."; i.className = "msg warn"; return; }
if (k.ok) { i.textContent = "Chave encontrada, permissao correta."; i.className = "msg ok"; }
else { i.textContent = "Permissao aberta. Rode: chmod 400 \"" + p.replace("~", "$HOME") + "\""; i.className = "msg warn"; }
}
function resetForm() {
editing = null; $("f").reset(); $("porta").value = 22;
$("ft").textContent = "Novo servidor"; $("save").textContent = "Salvar servidor"; $("cancel").hidden = true;
$("keyinfo").textContent = ""; updateAuth();
}
function startEdit(gi, si) {
const g = state.groups[gi], s = g.servers[si];
editing = [gi, si];
$("ft").textContent = "Editar servidor"; $("save").textContent = "Salvar alteracoes"; $("cancel").hidden = false;
$("grupo").value = g.name; $("nome").value = s.name; $("host").value = s.host;
$("porta").value = s.port || 22; $("usuario").value = s.user || "";
document.querySelector("input[name=auth][value=" + authOf(s) + "]").checked = true;
$("keypath").value = s.key || ""; $("keysel").value = s.key || "";
updateAuth(); showKey(); say("", ""); $("nome").focus(); window.scrollTo({top: 0, behavior: "smooth"});
}
$("cancel").onclick = () => { resetForm(); say("", ""); };
async function reload() { state = await api("/api/state"); render(); }
$("f").addEventListener("submit", async (ev) => {
ev.preventDefault();
const a = document.querySelector("input[name=auth]:checked").value;
const body = {group: $("grupo").value, name: $("nome").value, host: $("host").value, port: $("porta").value, user: $("usuario").value, auth: a, key: $("keypath").value, orig: editing};
try {
const r = await api("/api/save", {method: "POST", body});
state = r.state; render();
const warn = r.warnings && r.warnings.length ? " Atencao: " + r.warnings.join(" ") : "";
resetForm(); say("Servidor salvo." + warn, warn ? "warn" : "ok");
} catch (e) { say(e.message, "err"); }
});
async function ping(host, port, isSft) {
if (isSft) { say("Servidores ASA nao usam porta direta; teste com: sft ssh " + host, "warn"); return; }
say("Testando " + host + ":" + port + "...", "");
try {
const r = await api("/api/ping?host=" + encodeURIComponent(host) + "&port=" + encodeURIComponent(port));
say(r.open ? host + ":" + port + " respondeu." : host + ":" + port + " nao respondeu (" + r.detail + "). Verifique VPN e rede.", r.open ? "ok" : "err");
} catch (e) { say(e.message, "err"); }
}
$("test").onclick = () => ping($("host").value.trim(), $("porta").value || 22, false);
async function del(gi, si, name) {
if (!confirm("Excluir o servidor " + name + "?")) return;
try { const r = await api("/api/delete", {method: "POST", body: {gi, si}}); state = r.state; if (editing) resetForm(); render(); say("Servidor excluido.", "ok"); }
catch (e) { say(e.message, "err"); }
}
$("quit").onclick = async () => {
try { await api("/api/quit", {method: "POST", body: {}}); } catch (e) {}
document.body.textContent = "Formulario encerrado. Pode fechar esta aba.";
};
updateAuth();
reload().catch((e) => say(e.message, "err"));
</script>
</body>
</html>
"""

def tilde(path):
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path.startswith(home + os.sep) else path

def scan_keys():
    dirs = list(KEY_DIRS)
    data, _ = load()
    if data:
        for g in data["groups"]:
            for s in g.get("servers", []):
                if s.get("key"):
                    d = os.path.dirname(os.path.expanduser(s["key"]))
                    if d and tilde(d) not in dirs and d not in dirs:
                        dirs.append(tilde(d))
    seen, out = set(), []
    skip = {"config", "known_hosts", "known_hosts.old", "authorized_keys"}
    for d in dirs:
        base = os.path.expanduser(d)
        try:
            names = sorted(os.listdir(base))
        except OSError:
            continue
        for n in names:
            p = os.path.join(base, n)
            if n in skip or n.endswith(".pub") or n.startswith(".") or p in seen:
                continue
            try:
                if not os.path.isfile(p) or os.path.getsize(p) > 20000:
                    continue
                if not (n.endswith(".pem") or n.startswith("id_")):
                    continue
                ok = (os.stat(p).st_mode & 0o077) == 0
            except OSError:
                continue
            seen.add(p)
            out.append({"path": tilde(p), "ok": ok})
    return out

def write_inventory(data):
    with WRITE_LOCK:
        os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
        if os.path.exists(CONFIG):
            with open(CONFIG, "rb") as src, open(CONFIG + ".bak", "wb") as dst:
                dst.write(src.read())
            os.chmod(CONFIG + ".bak", 0o600)
        tmp = CONFIG + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, CONFIG)

def ui_state():
    data, err = load()
    if err:
        raise ValueError("Inventario invalido: %s" % err)
    return {"groups": data["groups"], "keys": scan_keys(), "config": tilde(CONFIG)}

def parse_form(p):
    group = str(p.get("group", "")).strip()
    name = str(p.get("name", "")).strip()
    host = str(p.get("host", "")).strip()
    user = str(p.get("user", "")).strip()
    auth = p.get("auth")
    
    if not group or not NAME_RE.match(group):
        raise ValueError("Informe o grupo (ate 60 caracteres).")
    if not name or not NAME_RE.match(name) or "|" in name:
        raise ValueError("Informe o nome (ate 60 caracteres, sem o caractere |).")
    if not HOST_RE.match(host):
        raise ValueError("IP ou hostname invalido.")
    if auth not in ("key", "password", "sft"):
        raise ValueError("Escolha como autenticar.")
    
    warnings = []
    if auth == "sft":
        return group, {"name": name, "type": "sft", "host": host}, warnings
    
    try:
        port = int(p.get("port") or 22)
    except (TypeError, ValueError):
        raise ValueError("Porta invalida.")
    if not 1 <= port <= 65535:
        raise ValueError("A porta deve estar entre 1 e 65535.")
    if not USER_RE.match(user):
        raise ValueError("Informe o usuario.")
    
    srv = {"name": name, "host": host, "user": user}
    if port != 22:
        srv["port"] = port
    
    if auth == "key":
        key = str(p.get("key", "")).strip().strip('"').strip("'")
        if not key or "\n" in key or "\x00" in key:
            raise ValueError("Informe o caminho do arquivo .pem.")
        srv["key"] = tilde(os.path.expanduser(key))
        problem = check_key(srv)
        if problem:
            warnings.append(problem + ".")
    
    return group, srv, warnings

def apply_save(payload):
    group, srv, warnings = parse_form(payload)
    data, err = load()
    if err:
        raise ValueError("Inventario invalido: %s" % err)
    
    orig = payload.get("orig")
    removed = None
    if isinstance(orig, list) and len(orig) == 2:
        try:
            removed = data["groups"][int(orig[0])]["servers"].pop(int(orig[1]))
        except (IndexError, KeyError, TypeError, ValueError):
            removed = None
    
    for g in data["groups"]:
        for s in g.get("servers", []):
            if s["name"].lower() == srv["name"].lower():
                if removed is not None:
                    data["groups"][int(orig[0])]["servers"].insert(int(orig[1]), removed)
                raise ValueError("Ja existe um servidor com o nome %s." % srv["name"])
    
    target = next((g for g in data["groups"] if g.get("name") == group), None)
    if target is None:
        target = {"name": group, "servers": []}
        data["groups"].append(target)
    
    target.setdefault("servers", []).append(srv)
    data["groups"] = [g for g in data["groups"] if g.get("servers")]
    write_inventory(data)
    return warnings

def apply_delete(payload):
    data, err = load()
    if err:
        raise ValueError("Inventario invalido: %s" % err)
    try:
        data["groups"][int(payload["gi"])]["servers"].pop(int(payload["si"]))
    except (IndexError, KeyError, TypeError, ValueError):
        raise ValueError("Servidor nao encontrado.")
    data["groups"] = [g for g in data["groups"] if g.get("servers")]
    write_inventory(data)

class UIHandler(BaseHTTPRequestHandler):
    server_version = "SSHMenu"
    def log_message(self, *args): pass
    
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)
    
    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False))
    
    def _allowed(self, url, need_header):
        port = self.server.server_address[1]
        if self.headers.get("Host", "") not in ("127.0.0.1:%d" % port, "localhost:%d" % port):
            return False
        if need_header:
            tok = self.headers.get("X-Token", "")
        else:
            tok = (parse_qs(url.query).get("t") or [""])[0]
        return secrets.compare_digest(tok, self.server.token)
    
    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 65536:
            raise ValueError("Pedido grande demais.")
        return json.loads(self.rfile.read(n) or b"{}")
    
    def do_GET(self):
        url = urlparse(self.path)
        self.server.last = time.time()
        if url.path == "/":
            if not self._allowed(url, False):
                return self._send(403, "Acesso negado.", "text/plain; charset=utf-8")
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if not self._allowed(url, True):
            return self._json(403, {"error": "Acesso negado."})
        try:
            if url.path == "/api/state":
                return self._json(200, ui_state())
            if url.path == "/api/ping":
                q = parse_qs(url.query)
                host = (q.get("host") or [""])[0]
                port = int((q.get("port") or ["22"])[0])
                if not HOST_RE.match(host) or not 1 <= port <= 65535:
                    return self._json(400, {"error": "Host ou porta invalidos."})
                try:
                    socket.create_connection((host, port), timeout=3).close()
                    return self._json(200, {"open": True, "detail": ""})
                except OSError as e:
                    return self._json(200, {"open": False, "detail": str(e)})
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        self._json(404, {"error": "Nao encontrado."})
    
    def do_POST(self):
        url = urlparse(self.path)
        self.server.last = time.time()
        if not self._allowed(url, True):
            return self._json(403, {"error": "Acesso negado."})
        try:
            payload = self._body()
            if url.path == "/api/save":
                warnings = apply_save(payload)
                return self._json(200, {"state": ui_state(), "warnings": warnings})
            if url.path == "/api/delete":
                apply_delete(payload)
                return self._json(200, {"state": ui_state()})
            if url.path == "/api/quit":
                self._json(200, {"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
        except (ValueError, OSError) as e:
            return self._json(400, {"error": str(e)})
        self._json(404, {"error": "Nao encontrado."})

def run_ui():
    ensure_inventory()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), UIHandler)
    srv.token = secrets.token_urlsafe(16)
    srv.last = time.time()
    url = "http://127.0.0.1:%d/?t=%s" % (srv.server_address[1], srv.token)
    
    def watchdog():
        while True:
            time.sleep(5)
            if time.time() - srv.last > IDLE_SECONDS:
                srv.shutdown()
                return
    threading.Thread(target=watchdog, daemon=True).start()
    print("Formulario em %s" % url)
    print("Ele fecha sozinho apos 15 minutos sem uso. Ctrl+C para encerrar.")
    try:
        if IS_LINUX:
            subprocess.run(["xdg-open", url], check=False)
        elif IS_MAC:
            subprocess.run(["open", url], check=False)
    except FileNotFoundError:
        print("Abra o endereco acima no navegador.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()

def run_indicator():
    if not IS_LINUX:
        print("Menu na barra so disponivel no Linux.")
        return
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        gi.require_version('AppIndicator3', '0.1')
        from gi.repository import Gtk, AppIndicator3
    except (ImportError, ValueError) as e:
        print("Erro: Instale python3-gi e gir1.2-appindicator3-0.1")
        print("sudo apt install python3-gi gir1.2-appindicator3-0.1")
        return
    
    indicator = AppIndicator3.Indicator.new("ssh-menu", "utilities-terminal", AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
    indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
    menu = Gtk.Menu()
    
    def rebuild_menu():
        for child in menu.get_children():
            menu.remove(child)
        data, err = load()
        if err:
            item = Gtk.MenuItem(label="Erro: %s" % err)
            menu.append(item)
        else:
            for gi_idx, g in enumerate(data["groups"]):
                submenu = Gtk.Menu()
                for si_idx, s in enumerate(g.get("servers", [])):
                    label = "%s (%s)" % (s["name"], s.get("user", "") + "@" + s["host"] if s.get("user") else s["host"])
                    item = Gtk.MenuItem(label=label)
                    ref = "%d:%d" % (gi_idx, si_idx)
                    item.connect("activate", lambda w, r=ref: open_in_terminal(r))
                    submenu.append(item)
                group_item = Gtk.MenuItem(label=g.get("name", "Sem grupo"))
                group_item.set_submenu(submenu)
                menu.append(group_item)
            menu.append(Gtk.SeparatorMenuItem())
            item_ui = Gtk.MenuItem(label="Gerenciar servidores")
            item_ui.connect("activate", lambda w: run_ui())
            menu.append(item_ui)
            item_reload = Gtk.MenuItem(label="Recarregar")
            item_reload.connect("activate", lambda w: rebuild_menu())
            menu.append(item_reload)
            item_quit = Gtk.MenuItem(label="Sair")
            item_quit.connect("activate", Gtk.main_quit)
            menu.append(item_quit)
        menu.show_all()
    
    rebuild_menu()
    indicator.set_menu(menu)
    Gtk.main()

def main():
    a = sys.argv[1:]
    if not a:
        if sys.stdin.isatty():
            pick()
        else:
            print("SSH Menu")
            print("Use: ssh-menu.py [open|run|list|ui|indicator]")
    elif a[0] == "open" and len(a) > 1:
        open_in_terminal(a[1])
    elif a[0] == "run" and len(a) > 1:
        run_here(a[1])
    elif a[0] == "ui":
        run_ui()
    elif a[0] == "indicator":
        run_indicator()
    elif a[0] == "list":
        data, err = load()
        if err:
            sys.exit("Erro no inventario: %s" % err)
        for g, s in flat(data):
            print("[%s] %s -> %s" % (g, s["name"], " ".join(build_cmd(s))))
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
