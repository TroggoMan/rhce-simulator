#!/bin/bash
# Stands up the rhce-simulator VM lab: 4 Rocky Linux 10 VMs via Vagrant,
# with SELinux enforcing and a spare blank disk on one node — the two
# things the Docker lab structurally cannot provide.
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
# Works on Linux, macOS and Windows (from inside WSL2). Nothing is
# installed without asking first.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAGRANT_DIR="$SCRIPT_DIR/../vagrant"
WORKDIR="${RHCE_SIM_WORKDIR:-$HOME/ansible}"
ROOT_PASSWORD="${RHCE_LAB_ROOT_PASSWORD:-rhce-lab}"
NODES=(kirk spock mccoy scotty)

log()  { printf '\033[36m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[33m!!\033[0m %s\n' "$1"; }
die()  { printf '\033[31mERROR:\033[0m %s\n' "$1" >&2; exit 1; }

confirm() {
    read -r -p "$1 [Y/n] " reply
    [[ -z "$reply" || "$reply" =~ ^[Yy] ]]
}

# ---------------------------------------------------------------------------
# 0. Reset the workdir to exam-blank
# ---------------------------------------------------------------------------
# Nothing about spinning up the VM lab ever touches $WORKDIR, so leftover
# playbooks/inventory/keys from a PAST session silently survive into a new
# one and stop it from actually being exam-like.
"$SCRIPT_DIR/reset-workdir.sh"

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

# ansible-core ships no collections at all. Most of the task catalog needs
# ansible.posix (firewalld/mount/seboolean/authorized_key) and
# community.general (lvol/lvg/parted/seport/sefcontext/archive) — without
# them a candidate's correct playbook fails with "couldn't resolve
# module/action", which reads like their own mistake.
if command -v ansible-galaxy &>/dev/null; then
    if ansible-galaxy collection list 2>/dev/null | grep -q "ansible.posix"; then
        :
    elif confirm "Install the ansible.posix + community.general collections most tasks need?"; then
        ansible-galaxy collection install ansible.posix community.general \
            || warn "Collection install failed — run it yourself before practising:
      ansible-galaxy collection install ansible.posix community.general"
    else
        warn "Skipping — install later with:"
        warn "  ansible-galaxy collection install ansible.posix community.general"
    fi
fi

export RHCE_LAB_ROOT_PASSWORD="$ROOT_PASSWORD"

# ---------------------------------------------------------------------------
# 2. Boot the VMs
# ---------------------------------------------------------------------------

# A host firewall that drops traffic on the libvirt bridge stops the VMs
# getting a DHCP lease, and Vagrant reports that only as "Waiting for domain
# to get an IP address..." forever — with no hint that a firewall is
# involved. Warn up front rather than letting it hang.
if [[ "$PROVIDER" == "libvirt" ]] && command -v ufw &>/dev/null; then
    if sudo ufw status 2>/dev/null | grep -qi "^Status: active" \
       && ! sudo ufw status 2>/dev/null | grep -qi virbr; then
        warn "ufw is active and has no rule for libvirt's bridge."
        warn "The VMs will boot but never get an IP. Allow it with:"
        echo "      sudo ufw allow in on virbr1"
        echo "      sudo ufw route allow in on virbr1"
        warn "(virbr1 is a private NAT bridge — this exposes nothing to your LAN.)"
        confirm "Add those two rules now?" && {
            sudo ufw allow in on virbr1 comment "libvirt lab VMs -> host DHCP/DNS" || true
            sudo ufw route allow in on virbr1 comment "libvirt lab VMs -> outbound" || true
        }
    fi
fi

# A previous run that failed partway (or a teardown that predates the fix
# for this) can leave a disk volume in libvirt's storage pool with no VM
# ever created for it — Vagrant never considered that machine "created", so
# nothing here or in vm-lab-teardown.sh would have cleaned it up. Left in
# place, it makes `vagrant up` fail outright with "storage volume ... exists
# already" for a reason that isn't obvious from the error. Clear it first.
if [[ "$PROVIDER" == "libvirt" ]] && command -v virsh &>/dev/null; then
    existing_vols="$(virsh -c qemu:///system vol-list --pool default 2>/dev/null | awk 'NR>2 {print $1}')"
    for name in "${NODES[@]}"; do
        virsh -c qemu:///system dominfo "vagrant_$name" &>/dev/null && continue
        for vol in "vagrant_${name}.img" "vagrant_${name}-vdb.qcow2"; do
            if grep -qx "$vol" <<<"$existing_vols"; then
                warn "Orphaned disk volume $vol with no matching VM — removing it"
                warn "so vagrant up can recreate $name cleanly."
                virsh -c qemu:///system vol-delete --pool default "$vol" &>/dev/null || true
            fi
        done
    done
fi

log "Booting ${#NODES[@]} Rocky Linux 10 VMs — first run downloads a ~1GB box."
cd "$VAGRANT_DIR"
vagrant up --provider="$PROVIDER"

# ---------------------------------------------------------------------------
# 3. Read back each node's bootstrap connection details from Vagrant's own
#    SSH config — NOT written anywhere as an inventory. What you do with
#    these is your first task.
# ---------------------------------------------------------------------------

declare -a HOSTS PORTS
for name in "${NODES[@]}"; do
    cfg="$(vagrant ssh-config "$name" 2>/dev/null)"
    host="$(awk '/^[[:space:]]*HostName/ {print $2; exit}' <<<"$cfg")"
    port="$(awk '/^[[:space:]]*Port/ {print $2; exit}' <<<"$cfg")"
    [[ -n "$host" && -n "$port" ]] || die "could not read ssh-config for $name"
    HOSTS+=("$host"); PORTS+=("$port")
done

# ---------------------------------------------------------------------------
# 4. Report what the lab can actually grade
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

# Spare-disk device naming follows the virtual disk bus (virtio -> vdb,
# SATA/SCSI -> sdb), so detect it rather than assume: naming the wrong one
# makes the storage task silently gradeable-but-meaningless.
SPARE=""
for candidate in vdb sdb; do
    if vagrant ssh scotty -c "test -b /dev/$candidate" &>/dev/null; then
        SPARE="/dev/$candidate"; break
    fi
done

echo
printf '\033[1;33m%s\033[0m\n' "============================================================"
printf '\033[1;33m%s\033[0m\n' " VM LAB IS UP — BOOTSTRAP ACCESS ONLY, NOT AN INVENTORY"
printf '\033[1;33m%s\033[0m\n' "============================================================"
echo "No automation user, no SSH key, no inventory file were created."
echo "Every node hands you exactly what the real exam hands you: root,"
echo "reachable by password. Turning THAT into a working Ansible setup"
echo "is your first task, not something this script does for you."
echo
printf '  %-8s %-22s %s\n' "NODE" "SSH" "ROOT PASSWORD"
for i in "${!NODES[@]}"; do
    printf '  %-8s ssh -p %-5s root@%-9s %s\n' \
        "${NODES[$i]}" "${PORTS[$i]}" "${HOSTS[$i]}" "$ROOT_PASSWORD"
done
echo
echo "From here:"
echo "  1. Write your OWN $WORKDIR/inventory using the node/SSH details above."
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
echo "else grades against it too. RHCE_SIM_NODES doesn't need exporting —"
echo "the simulator sees these VMs running via 'vagrant status' and uses"
echo "them automatically; only set it yourself to override:"
echo "    export RHCE_SIM_NODES=\"$(IFS=,; echo "${NODES[*]}")\"   # match your inventory's hostnames"
echo "    export RHCE_SIM_WORKDIR=\"$WORKDIR\""
if [[ -n "$SPARE" ]]; then
    echo "    export RHCE_SIM_SPARE_DISK=\"$SPARE\"   # spare disk detected on scotty"
else
    warn "No spare disk found — the storage task will report its state checks"
    warn "as skipped. Re-run without RHCE_LAB_EXTRA_DISK=0 to attach one."
fi
echo "    python3 rhce_simulator.py --practice selinux"
echo

log "When you're done, from anywhere:"
echo "    $SCRIPT_DIR/vm-lab-teardown.sh            # power the VMs off, keep them"
echo "    $SCRIPT_DIR/vm-lab-teardown.sh --destroy  # delete them entirely"
echo
log "Bare vagrant commands only work from $VAGRANT_DIR — run them anywhere else"
log "and Vagrant silently acts on a different (or nonexistent) machine:"
echo "    vagrant reload      # reboot (needed after an SELinux relabel)"
