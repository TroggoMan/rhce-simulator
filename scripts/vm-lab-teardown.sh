#!/bin/bash
# Stops or deletes the rhce-simulator VM lab.
#
# The whole point of this script is that it works from ANY directory. Vagrant
# is directory-scoped: it acts on whichever Vagrantfile it finds by walking up
# from $PWD, so `vagrant halt` run from the repo root does nothing to a lab
# defined in vagrant/. Worse, if a stray Vagrantfile exists up there (a stray
# `vagrant init`, say), Vagrant finds it, sees a machine named "default" that
# was never created, and exits 0 having touched nothing — the VMs keep running
# and there's no error to tell you why.
#
#   ./scripts/vm-lab-teardown.sh            # power the VMs off, keep them
#   ./scripts/vm-lab-teardown.sh --destroy  # delete them and their disks
#   ./scripts/vm-lab-teardown.sh --status   # just show what's running
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VAGRANT_DIR="$REPO_DIR/vagrant"
NODES=(morty summer jerry)

log()  { printf '\033[36m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[33m!!\033[0m %s\n' "$1"; }
die()  { printf '\033[31mERROR:\033[0m %s\n' "$1" >&2; exit 1; }

ACTION=halt
case "${1:-}" in
    "")                   ACTION=halt ;;
    -d|--destroy)         ACTION=destroy ;;
    -s|--status)          ACTION=status ;;
    -h|--help)            sed -n '2,18p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *)                    die "unknown option '$1' (try --help)" ;;
esac

command -v vagrant &>/dev/null || die "Vagrant not found on PATH."
[[ -f "$VAGRANT_DIR/Vagrantfile" ]] || die "No Vagrantfile at $VAGRANT_DIR."

# Vagrant reads VAGRANT_CWD in preference to walking up from $PWD, so this
# targets the lab correctly no matter where the caller invoked us from, and
# is immune to stray Vagrantfiles in parent directories.
export VAGRANT_CWD="$VAGRANT_DIR"

# Flag those stray Vagrantfiles if they exist — they are inert here thanks to
# VAGRANT_CWD, but they will bite anyone running vagrant by hand.
for stray in "$REPO_DIR/Vagrantfile" "$SCRIPT_DIR/Vagrantfile"; do
    if [[ -f "$stray" ]] && grep -q '^ *config\.vm\.box *= *"base"' "$stray" 2>/dev/null; then
        warn "Stray 'vagrant init' Vagrantfile at ${stray/#$REPO_DIR\//}"
        warn "Running vagrant by hand from that directory silently does nothing."
        warn "Delete it and its .vagrant/ sibling."
    fi
done

# Vagrant's libvirt provider prints fog warnings on every invocation that have
# nothing to do with the lab; drop them so real output stands out.
run_vagrant() { vagrant "$@" 2>&1 | grep -v '^\[fog\]' || true; }

if [[ "$ACTION" == "status" ]]; then
    run_vagrant status
    exit 0
fi

if [[ "$ACTION" == "destroy" ]]; then
    log "Destroying the VM lab (deletes the VMs and their disks)."
    run_vagrant destroy -f
else
    log "Powering off the VM lab (VMs are kept — bring them back with vm-lab-setup.sh)."
    run_vagrant halt
fi

# ---------------------------------------------------------------------------
# Verify, rather than trusting the exit code
# ---------------------------------------------------------------------------
# `vagrant halt` reports success for a machine it merely couldn't find, which
# is exactly the failure this script exists to prevent. Ask the hypervisor.

leftovers=()
if command -v virsh &>/dev/null; then
    for name in "${NODES[@]}"; do
        state="$(virsh -c qemu:///system domstate "vagrant_$name" 2>/dev/null | head -1 | tr -d '\r')"
        [[ "$state" == "running" || "$state" == "paused" ]] && leftovers+=("vagrant_$name ($state)")
    done
fi
if command -v VBoxManage &>/dev/null; then
    for name in "${NODES[@]}"; do
        VBoxManage list runningvms 2>/dev/null | grep -q "_${name}_" && leftovers+=("$name (virtualbox)")
    done
fi

if [[ ${#leftovers[@]} -gt 0 ]]; then
    warn "These VMs are still running after '$ACTION':"
    printf '      %s\n' "${leftovers[@]}"
    warn "That usually means they were created from a different directory."
    warn "Force them off with:"
    echo "      virsh -c qemu:///system destroy vagrant_<name>     # libvirt"
    echo "      VBoxManage controlvm <name> poweroff               # virtualbox"
    exit 1
fi

if [[ "$ACTION" == "destroy" ]]; then
    log "Lab destroyed — no VM processes remain."
    log "The inventory at \${RHCE_SIM_WORKDIR:-\$HOME/ansible} is left in place;"
    log "re-run scripts/vm-lab-setup.sh to rebuild the VMs and rewrite it."
else
    log "Lab is powered off — no VM processes remain."
    log "Bring it back with: $SCRIPT_DIR/vm-lab-setup.sh"
fi
