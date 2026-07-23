#!/bin/bash
# Stands up the rhce-simulator Docker lab: 5 Rocky Linux 10 (systemd-enabled)
# managed nodes reachable over SSH on 127.0.0.1:2201-2205, plus an
# inventory + ansible.cfg written into $RHCE_SIM_WORKDIR. Checks for
# Docker and ansible-core and offers to install what's missing (nothing is
# installed without asking first).
#
# Windows: run this from inside WSL2, not native PowerShell/cmd — Ansible's
# control node doesn't run natively on Windows. Docker Desktop's WSL2
# backend makes `docker` work from a WSL prompt automatically.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$SCRIPT_DIR/../docker"
WORKDIR="${RHCE_SIM_WORKDIR:-$HOME/ansible}"
REMOTE_USER="${RHCE_SIM_REMOTE_USER:-devops}"
NODES=(morty summer jerry beth rick)
BASE_PORT=2201
KEY_PATH="$HOME/.ssh/rhce_lab"

log()  { printf '\033[36m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[33m!!\033[0m %s\n' "$1"; }
die()  { printf '\033[31mERROR:\033[0m %s\n' "$1" >&2; exit 1; }

confirm() {
    read -r -p "$1 [Y/n] " reply
    [[ -z "$reply" || "$reply" =~ ^[Yy] ]]
}

# ---------------------------------------------------------------------------
# 1. Prerequisites
# ---------------------------------------------------------------------------

if grep -qi microsoft /proc/version 2>/dev/null; then
    OS=wsl
elif [[ "$(uname -s)" == "Darwin" ]]; then
    OS=mac
else
    OS=linux
fi

if ! command -v docker &>/dev/null; then
    warn "Docker not found."
    case "$OS" in
        linux)
            if confirm "Install Docker via the official convenience script (get.docker.com)?"; then
                curl -fsSL https://get.docker.com | sudo sh
                sudo usermod -aG docker "$USER"
                warn "Added $USER to the docker group — log out/in (or run 'newgrp docker') before re-running this script."
                exit 0
            fi
            ;;
        mac)
            warn "Install Docker Desktop for Mac: https://docs.docker.com/desktop/setup/install/mac-install/"
            ;;
        wsl)
            warn "Install Docker Desktop for Windows with the WSL2 backend enabled: https://docs.docker.com/desktop/setup/install/windows-install/"
            warn "Once installed, 'docker' will work from this WSL prompt automatically."
            ;;
    esac
    die "Install Docker, then re-run this script."
fi

if ! docker compose version &>/dev/null; then
    die "Docker is installed but the 'docker compose' plugin isn't available. Update Docker Desktop / install docker-compose-plugin."
fi

if ! command -v ansible-playbook &>/dev/null; then
    warn "ansible-core not found."
    if confirm "Install ansible-core + ansible-navigator via 'pip install --user'?"; then
        python3 -m pip install --user ansible-core ansible-navigator
        export PATH="$HOME/.local/bin:$PATH"
    else
        die "ansible-core is required to run the simulator itself."
    fi
fi

# ---------------------------------------------------------------------------
# 2. SSH key for lab access
# ---------------------------------------------------------------------------

if [[ ! -f "$KEY_PATH" ]]; then
    log "Generating lab SSH keypair at $KEY_PATH"
    ssh-keygen -t ed25519 -N "" -f "$KEY_PATH" -C "rhce-lab" -q
fi

# ---------------------------------------------------------------------------
# 3. Build and start the lab
# ---------------------------------------------------------------------------

log "Building and starting the lab (${NODES[*]})..."
RHCE_SIM_REMOTE_USER="$REMOTE_USER" docker compose -f "$DOCKER_DIR/docker-compose.yml" up -d --build

log "Waiting for sshd in each container..."
for i in "${!NODES[@]}"; do
    port=$((BASE_PORT + i))
    for attempt in $(seq 1 30); do
        if docker exec "${NODES[$i]}" systemctl is-active sshd &>/dev/null; then
            break
        fi
        [[ "$attempt" -eq 30 ]] && die "sshd never came up in ${NODES[$i]}"
        sleep 1
    done
done

log "Installing the lab public key into each node..."
PUBKEY="$(cat "$KEY_PATH.pub")"
for name in "${NODES[@]}"; do
    docker exec "$name" bash -c "
        mkdir -p /home/$REMOTE_USER/.ssh
        echo '$PUBKEY' > /home/$REMOTE_USER/.ssh/authorized_keys
        chmod 600 /home/$REMOTE_USER/.ssh/authorized_keys
        chown -R $REMOTE_USER:$REMOTE_USER /home/$REMOTE_USER/.ssh
    "
done

# ---------------------------------------------------------------------------
# 4. Inventory + ansible.cfg
# ---------------------------------------------------------------------------

mkdir -p "$WORKDIR"

for f in inventory ansible.cfg; do
    if [[ -f "$WORKDIR/$f" ]]; then
        cp "$WORKDIR/$f" "$WORKDIR/$f.bak.$(date +%s)"
        warn "Backed up existing $WORKDIR/$f"
    fi
done

{
    echo "[lab]"
    for i in "${!NODES[@]}"; do
        port=$((BASE_PORT + i))
        echo "${NODES[$i]} ansible_host=127.0.0.1 ansible_port=$port ansible_user=$REMOTE_USER ansible_ssh_private_key_file=$KEY_PATH ansible_python_interpreter=/usr/bin/python3"
    done
} > "$WORKDIR/inventory"

cat > "$WORKDIR/ansible.cfg" <<EOF
[defaults]
inventory = $WORKDIR/inventory
host_key_checking = False
remote_user = $REMOTE_USER
EOF

log "Lab is up. Nodes: ${NODES[*]} (SSH on 127.0.0.1:$BASE_PORT-$((BASE_PORT + ${#NODES[@]} - 1)))"
log "Wrote $WORKDIR/inventory and $WORKDIR/ansible.cfg"
log "export RHCE_SIM_NODES=\"$(IFS=,; echo "${NODES[*]}")\"  # then run rhce_simulator.py"
