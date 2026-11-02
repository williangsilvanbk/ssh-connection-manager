# SSH Connection Manager

A local SSH connection manager for **macOS** and **Linux (Ubuntu Desktop)**.

It reads a list of servers from a JSON file and opens the SSH session in the terminal. It does not use the cloud, does not store passwords, and requires no external dependencies — just a Python 3 script.

## Features
- ✅ **100% local** — inventory stays on your machine
- ✅ **No stored passwords** — use `.pem` keys or terminal prompt
- ✅ **Zero dependencies** — only Python 3
- ✅ **Taskbar menu** — SwiftBar/xbar on Mac, AppIndicator on Ubuntu
- ✅ **Local web UI** — manage servers via browser
- ✅ **Connectivity test** — checks if the port is open
- ✅ **Automatic backup** — creates `servers.json.bak`
- ✅ **ASA/ScaleFT support** — integrates with `sft ssh`

## Installation

### macOS
mkdir -p ~/bin ~/.config/ssh-menu
cp ssh-menu.1h.py ~/bin/ssh-menu.1h.py
chmod +x ~/bin/ssh-menu.1h.py
echo 'alias conectar="~/bin/ssh-menu.1h.py"' >> ~/.zshrc

### Linux (Ubuntu)
mkdir -p ~/bin ~/.config/ssh-menu
cp ssh-menu.py ~/bin/ssh-menu.py
chmod +x ~/bin/ssh-menu.py
echo 'alias conectar="~/bin/ssh-menu.py"' >> ~/.bashrc
sudo apt install python3-gi gir1.2-appindicator3-0.1 libnotify-bin

## Usage
- `conectar` : Lists servers and connects
- `conectar list` : Shows commands for each server
- `conectar run <name>` : Connects directly
- `conectar ui` : Opens web UI to manage servers
- `conectar indicator` : Starts taskbar menu (Linux)

## Security
- 🔒 Never store passwords in the inventory.
- 🔒 Keys must have `chmod 400` permissions.
- 🔒 Web UI is bound to `127.0.0.1` with a random port and token.

## License
MIT — See the [LICENSE](LICENSE) file.
