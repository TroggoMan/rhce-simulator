#!/bin/bash
# Stands up the rhce-simulator VM lab: 3 Rocky Linux 10 VMs via Vagrant,
# with SELinux enforcing and a spare blank disk on one node — the two
# things the Docker lab structurally cannot provide.
#
# Writes an inventory + ansible.cfg into $RHCE_SIM_WORKDIR, exactly like
# scripts/lab-setup.sh does for the container lab, so the simulator itself
# doesn't care which lab you used.
#
# Works on Linux, macOS and Windows (from inside WSL2). Nothing is
# installed without asking first.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAGRANT_DIR="$SCRIPT_DIR/../vagrant"
WORKDIR="${RHCE_SIM_WORKDIR:-$HOME/ansible}"
REMOTE_USER="${RHCE_SIM_REMOTE_USER:-devops}"
KEY_PATH="$HOME/.ssh/rhce_lab"
NODES=(morty summer jerry)

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

command -v vagrant &>/dev/null || die \
"Vagrant not found. Install it, then re-run:
  Linux:  your package manager, or https://developer.hashicorp.com/vagrant/downloads
  macOS:  brew install --cask vagrant
  WSL2:   install Vagrant on WINDOWS (not inside WSL) — see the README's
          Windows notes, since Vagrant in WSL2 can't drive Hyper-V/VirtualBox
          on the Windows host without extra configuration."

if [[ "$OS" == "mac" && "$(uname -m)" == "arm64" ]]; then
    warn "Apple Silicon detected. VirtualBox support on arm64 is poor, and"
    warn "Rocky publishes no VMware Vagrant box. The Docker lab is the"
    warn "better path on this hardware — see the README. Continuing anyway."
fi

# Pick a provider: libvirt is the better Linux experience, VirtualBox is the
# portable default everywhere else.
PROVIDER="${RHCE_LAB_PROVIDER:-}"
if [[ -z "$PROVIDER" ]]; then
    if [[ "$OS" == "linux" ]] && vagrant plugin list 2>/dev/null | grep -q vagrant-libvirt; then
        PROVIDER=libvirt
    elif command -v VBoxManage &>/dev/null || command -v vboxmanage &>/dev/null; then
        PROVIDER=virtualbox
    elif [[ "$OS" == "linux" ]] && command -v virsh &>/dev/null; then
        warn "libvirt is present but the vagrant-libvirt plugin is not."
        if confirm "Install the vagrant-libvirt plugin now?"; then
            vagrant plugin install vagrant-libvirt
            PROVIDER=libvirt
        else
            die "Install either VirtualBox or the vagrant-libvirt plugin, then re-run."
        fi
    else
        die "No usable provider found. Install VirtualBox (portable) or, on
Linux, libvirt/KVM plus the vagrant-libvirt plugin. Override detection with
RHCE_LAB_PROVIDER=virtualbox|libvirt."
    fi
fi
log "Using Vagrant provider: $PROVIDER"

if ! command -v ansible-playbook &>/dev/null; then
    warn "ansible-core not found on this control node."
    if confirm "Install ansible-core + ansible-navigator via 'pip install --user'?"; then
        python3 -m pip install --user ansible-core ansible-navigator
        export PATH="$HOME/.local/bin:$PATH"
    else
        warn "Continuing without it — the simulator will grade your files"
        warn "statically but cannot run your playbooks."
    fi
fi

# ---------------------------------------------------------------------------
# 2. SSH key (shared with the Docker lab, so both use the same one)
# ---------------------------------------------------------------------------

if [[ ! -f "$KEY_PATH" ]]; then
    log "Generating lab SSH keypair at $KEY_PATH"
    ssh-keygen -t ed25519 -N "" -f "$KEY_PATH" -C "rhce-lab" -q
fi
export RHCE_LAB_PUBKEY="$(cat "$KEY_PATH.pub")"
export RHCE_SIM_REMOTE_USER="$REMOTE_USER"

# ---------------------------------------------------------------------------
# 3. Boot the VMs
# ---------------------------------------------------------------------------

log "Booting ${#NODES[@]} Rocky Linux 10 VMs — first run downloads a ~1GB box."
cd "$VAGRANT_DIR"
vagrant up --provider="$PROVIDER"

# ---------------------------------------------------------------------------
# 4. Inventory + ansible.cfg, derived from Vagrant's own SSH config
# ---------------------------------------------------------------------------
# Parsing `vagrant ssh-config` rather than hard-coding a private network
# keeps this identical across providers and avoids host-only networking
# setup entirely — every node ends up as 127.0.0.1 on a forwarded port,
# the same shape the Docker lab produces.

mkdir -p "$WORKDIR"
for f in inventory ansible.cfg; do
    if [[ -f "$WORKDIR/$f" ]]; then
        cp "$WORKDIR/$f" "$WORKDIR/$f.bak.$(date +%s)"
        warn "Backed up existing $WORKDIR/$f"
    fi
done

log "Writing $WORKDIR/inventory"
{
    echo "[lab]"
    for name in "${NODES[@]}"; do
        cfg="$(vagrant ssh-config "$name" 2>/dev/null)"
        host="$(awk '/^[[:space:]]*HostName/ {print $2; exit}' <<<"$cfg")"
        port="$(awk '/^[[:space:]]*Port/ {print $2; exit}' <<<"$cfg")"
        [[ -n "$host" && -n "$port" ]] || die "could not read ssh-config for $name"
        echo "$name ansible_host=$host ansible_port=$port ansible_user=$REMOTE_USER ansible_ssh_private_key_file=$KEY_PATH ansible_python_interpreter=/usr/bin/python3"
    done
} > "$WORKDIR/inventory"

cat > "$WORKDIR/ansible.cfg" <<EOF
[defaults]
inventory = $WORKDIR/inventory
host_key_checking = False
remote_user = $REMOTE_USER
EOF

# ---------------------------------------------------------------------------
# 5. Report what the lab can actually grade
# ---------------------------------------------------------------------------

log "Checking SELinux state (this is why you built VMs)"
needs_reload=0
for name in "${NODES[@]}"; do
    mode="$(vagrant ssh "$name" -c "getenforce" 2>/dev/null | tr -d '\r\n' || echo unknown)"
    printf '    %-8s SELinux: %s\n' "$name" "$mode"
    [[ "$mode" == "Enforcing" ]] || needs_reload=1
done

if [[ "$needs_reload" -eq 1 ]]; then
    warn "Not every node is Enforcing yet. If a node reported Disabled it has"
    warn "been flagged for a filesystem relabel — run 'vagrant reload' in"
    warn "$VAGRANT_DIR and it will come back Enforcing."
fi

echo
log "VM lab is up. Next:"
echo "    export RHCE_SIM_NODES=\"$(IFS=,; echo "${NODES[*]}")\""
echo "    export RHCE_SIM_WORKDIR=\"$WORKDIR\""
echo "    python3 rhce_simulator.py --practice selinux"
echo
log "Manage the lab from $VAGRANT_DIR:"
echo "    vagrant halt        # stop the VMs, keep them"
echo "    vagrant reload      # reboot (needed after an SELinux relabel)"
echo "    vagrant destroy -f  # delete them entirely"
