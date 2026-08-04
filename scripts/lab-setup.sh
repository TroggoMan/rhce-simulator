#!/bin/bash
# Stands up the rhce-simulator Docker lab: 5 Rocky Linux 10 (systemd-enabled)
# managed nodes reachable over SSH on 127.0.0.1:2201-2205. Checks for
# Docker and ansible-core and offers to install what's missing (nothing is
# installed without asking first).
#
# Deliberately does NOT write an inventory, ansible.cfg, or an automation
# user/SSH key for you. Every node comes up with EXAM-STYLE bootstrap
# access only: root, reachable by password. Building your own inventory,
# ansible.cfg, automation user, SSH key and sudoers from that bootstrap
# access is your actual first task — exactly what the real exam hands you
# and exactly what Domains 3/4 (Configure Ansible / Configure managed
# nodes) grade. This script prints what it provisioned; it doesn't do that
# part for you.
#
# Windows: run this from inside WSL2, not native PowerShell/cmd — Ansible's
# control node doesn't run natively on Windows. Docker Desktop's WSL2
# backend makes `docker` work from a WSL prompt automatically.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$SCRIPT_DIR/../docker"
WORKDIR="${RHCE_SIM_WORKDIR:-$HOME/ansible}"
ROOT_PASSWORD="${RHCE_LAB_ROOT_PASSWORD:-rhce-lab}"
NODES=(morty summer jerry beth rick)
BASE_PORT=2201

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
    warn "ansible-core not found on this host."
    warn "That is now OPTIONAL: the lab includes a control node container"
    warn "with ansible-core and rhel-system-roles already installed, and"
    warn "working from there is closer to the exam than your workstation is."
    warn "Install locally only if you would rather drive the lab from here."
    if confirm "Install ansible-core + ansible-navigator via 'pip install --user'?"; then
        python3 -m pip install --user ansible-core ansible-navigator
        export PATH="$HOME/.local/bin:$PATH"
    else
        warn "Skipping — work from the control node container instead."
    fi
fi

# ---------------------------------------------------------------------------
# 2. Build and start the lab
# ---------------------------------------------------------------------------

log "Building and starting the lab (${NODES[*]})..."
# UID/GID are passed through so the control node's user matches yours and
# bind-mounted playbooks don't come back owned by root on the host.
RHCE_LAB_ROOT_PASSWORD="$ROOT_PASSWORD" \
RHCE_LAB_UID="$(id -u)" RHCE_LAB_GID="$(id -g)" \
RHCE_SIM_WORKDIR="$WORKDIR" \
    docker compose -f "$DOCKER_DIR/docker-compose.yml" up -d --build

log "Waiting for sshd in each container..."
for i in "${!NODES[@]}"; do
    for attempt in $(seq 1 30); do
        if docker exec "${NODES[$i]}" systemctl is-active sshd &>/dev/null; then
            break
        fi
        [[ "$attempt" -eq 30 ]] && die "sshd never came up in ${NODES[$i]}"
        sleep 1
    done
done

# Rebuilt containers generate new SSH host keys but keep the same
# 127.0.0.1:220x address, so any entry left over from a previous lab reads
# as a man-in-the-middle attack and ssh refuses to connect. Note that
# host_key_checking = False does NOT cover this — it only skips prompting
# for an UNKNOWN key; a CHANGED one is a hard failure by design. Clear them
# so the very first bootstrap connection below can actually happen.
if command -v ssh-keygen &>/dev/null && [[ -f "$HOME/.ssh/known_hosts" ]]; then
    log "Forgetting any stale host keys for 127.0.0.1:${BASE_PORT}-$((BASE_PORT + ${#NODES[@]} - 1))..."
    hostkeys_failed=0
    for i in "${!NODES[@]}"; do
        ssh-keygen -R "[127.0.0.1]:$((BASE_PORT + i))" &>/dev/null || hostkeys_failed=1
    done
    # ssh-keygen -R refuses to rewrite the WHOLE file if ANY line in it is
    # malformed (a stray blank/CR-only line is enough), so this can fail
    # while looking like it worked. Say so rather than let the candidate
    # debug a MITM banner on their first bootstrap connection.
    if [[ "$hostkeys_failed" -eq 1 ]]; then
        warn "Couldn't clear old host keys from ~/.ssh/known_hosts."
        warn "ssh-keygen refuses to rewrite that file if any line in it is"
        warn "malformed; check it with: ssh-keygen -R '[127.0.0.1]:$BASE_PORT'"
        warn "Until it's fixed, connecting to the lab will fail with"
        warn "'REMOTE HOST IDENTIFICATION HAS CHANGED'."
    fi
fi

echo
printf '\033[1;33m%s\033[0m\n' "============================================================"
printf '\033[1;33m%s\033[0m\n' " DOCKER LAB IS UP — BOOTSTRAP ACCESS ONLY, NOT AN INVENTORY"
printf '\033[1;33m%s\033[0m\n' "============================================================"
echo "No automation user, no SSH key, no inventory file were created."
echo "Every node hands you exactly what the real exam hands you: root,"
echo "reachable by password. Turning THAT into a working Ansible setup"
echo "is your first task, not something this script does for you."
echo
printf '  %-8s %-24s %s\n' "NODE" "SSH" "ROOT PASSWORD"
for i in "${!NODES[@]}"; do
    port=$((BASE_PORT + i))
    printf '  %-8s ssh -p %-5s root@127.0.0.1 %s\n' "${NODES[$i]}" "$port" "$ROOT_PASSWORD"
done
echo
printf '\033[1m%s\033[0m\n' "  Or work from the control node, which is what the exam gives you:"
echo "      docker exec -it control bash"
echo "  It runs Rocky 10 with ansible-core and rhel-system-roles already"
echo "  installed — so redhat.rhel_system_roles.<role> resolves for real, on"
echo "  the ansible-core version RHEL ships rather than your workstation's."
echo "  Managed nodes are reachable from it as plain hostnames on port 22"
echo "  (morty, summer, jerry, beth, rick) — no 127.0.0.1:220x needed, and"
echo "  the inventory you write there looks like the one the exam wants."
echo "  $WORKDIR and this repo are both mounted inside it."
echo
echo "From here:"
echo "  1. Write your OWN $WORKDIR/inventory using the node details above."
echo "  2. Write your OWN $WORKDIR/ansible.cfg."
echo "  3. Bootstrap an automation user + SSH key + passwordless sudo on each"
echo "     node — connecting as root with -k (ask SSH pass) and -e ansible_password=..."
echo "     for that FIRST run only, then switch your inventory to key-based access."
echo "  4. Confirm it worked:  ansible all -m ping"
echo
echo "The simulator drills exactly this in --learn (Configuring managed nodes)"
echo "and grades it directly:"
echo "    python3 rhce_simulator.py --practice ansible_config"
echo "    python3 rhce_simulator.py --practice inventory"
echo "    python3 rhce_simulator.py --practice managed_nodes"
echo
echo "Once ansible all -m ping works against your own config, everything"
echo "else grades against it too:"
echo "    export RHCE_SIM_NODES=\"$(IFS=,; echo "${NODES[*]}")\"   # match your inventory's hostnames"
echo "    export RHCE_SIM_WORKDIR=\"$WORKDIR\""
echo
