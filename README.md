# SSH Menu

Gerenciador local de conexões SSH para **macOS** e **Linux (Ubuntu Desktop)**.

Lê uma lista de servidores de um arquivo JSON e abre a sessão SSH no terminal. Não usa nuvem, não grava senhas e não instala dependências externas — apenas um script Python 3.

## Características

- ✅ **100% local** — o inventário fica só na sua máquina (`~/.config/ssh-menu/servers.json`)
- ✅ **Sem senhas gravadas** — use chaves `.pem` ou o terminal pergunta a cada conexão
- ✅ **Zero dependências** — só Python 3 (já vem no macOS e na maioria das distros Linux)
- ✅ **Menu na barra de tarefas** — SwiftBar/xbar no Mac, AppIndicator no Ubuntu
- ✅ **Formulário web local** — cadastre servidores pelo navegador com um clique
- ✅ **Teste de conectividade** — verifica se a porta está aberta antes de conectar
- ✅ **Backup automático** — cada alteração gera um `servers.json.bak`
- ✅ **Suporte a ASA/ScaleFT** — integração com `sft ssh`

## Instalação

### macOS

```bash
mkdir -p ~/bin ~/.config/ssh-menu
cp ssh-menu.1h.py ~/bin/ssh-menu.1h.py
chmod +x ~/bin/ssh-menu.1h.py
echo 'alias conectar="~/bin/ssh-menu.1h.py"' >> ~/.zshrc
source ~/.zshrc
```

### Linux (Ubuntu Desktop)

```bash
mkdir -p ~/bin ~/.config/ssh-menu
cp ssh-menu.py ~/bin/ssh-menu.py
chmod +x ~/bin/ssh-menu.py
echo 'alias conectar="~/bin/ssh-menu.py"' >> ~/.bashrc
source ~/.bashrc

# Dependências opcionais (menu na barra e notificações)
sudo apt install python3-gi gir1.2-appindicator3-0.1 libnotify-bin
```

## Uso

```bash
conectar              # Lista servidores e conecta no terminal atual
conectar list         # Mostra o comando que cada servidor executa
conectar run nome     # Conecta direto, sem menu
conectar open nome    # Abre em uma nova aba do terminal
conectar ui           # Formulário web para cadastrar servidores
conectar indicator    # Menu na barra de tarefas (Linux)
```

## Formulário web

O comando `conectar ui` sobe um servidor HTTP **apenas em 127.0.0.1**, com:

- Porta aleatória e token na URL (proteção contra DNS rebinding)
- Detecção automática de chaves `.pem` em `~/.ssh` e outras pastas comuns
- Validação de permissões das chaves (`chmod 400`)
- Fecha sozinho após 15 minutos sem uso

## Formato do inventário

```json
{
  "groups": [
    {
      "name": "AWS",
      "servers": [
        {
          "name": "virt-ohio",
          "host": "10.0.0.10",
          "user": "ec2-user",
          "key": "~/.ssh/minha-chave.pem",
          "port": 22
        },
        {
          "name": "servidor-asa",
          "type": "sft",
          "host": "nome-no-asa"
        }
      ]
    }
  ]
}
```

- `name` e `host` são **obrigatórios**
- `user`, `key` e `port` são opcionais
- Sem `key`, o SSH pede a senha no terminal
- `"type": "sft"` usa `sft ssh <host>` (servidores ASA/ScaleFT)

## Segurança

- 🔒 **Nunca grave senhas no inventário** — use chaves ou o `sft`
- 🔒 Chaves precisam estar com `chmod 400` (o script avisa se estiver aberta)
- 🔒 Inventário criado com permissão `600` (só o dono lê)
- 🔒 Servidor web recusa conexões externas e valida token

## Licença

MIT — use, modifique e compartilhe livremente. Veja o arquivo [LICENSE](LICENSE).
