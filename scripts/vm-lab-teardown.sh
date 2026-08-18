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

# ---------------------------------------------------------------------------
# The optional control container vm-lab-setup.sh can pair with these VMs is
# managed by scripts/control-setup.sh, which this delegates to — only one
# 'control' container can exist at a time regardless of which lab paired
# it, so if it's here, it's ours to stop/destroy from whichever teardown
# runs. Best-effort — control-setup.sh itself tolerates a missing Docker
# rather than failing, so this never fails the VM teardown over it.
# ---------------------------------------------------------------------------
CONTROL_SETUP="$SCRIPT_DIR/control-setup.sh"

if [[ "$ACTION" == "status" ]]; then
    run_vagrant status
    echo
    "$CONTROL_SETUP" --status
    exit 0
fi

if [[ "$ACTION" == "destroy" ]]; then
    "$CONTROL_SETUP" --destroy
else
    "$CONTROL_SETUP" --stop
fi

if [[ "$ACTION" == "destroy" ]]; then
    log "Destroying the VM lab (deletes the VMs and their disks)."
    run_vagrant destroy -f
else
    log "Powering off the VM lab (VMs are kept — bring them back with vm-lab-setup.sh)."
    run_vagrant halt
fi

# ---------------------------------------------------------------------------
# vagrant-libvirt doesn't reliably clean up its own storage-pool volumes on
# destroy — especially the extra disk attached via lv.storage :file, and
# anything left behind by a vagrant up that failed partway (a volume can
# exist with no domain ever having been created for it, which `vagrant
# destroy` has nothing to act on since Vagrant never considered the machine
# "created"). A stray volume with a name vagrant-libvirt wants to reuse
# makes the NEXT `vagrant up` fail outright with "storage volume ... exists
# already" — purge them here so destroy actually leaves nothing behind.
# ---------------------------------------------------------------------------
if [[ "$ACTION" == "destroy" ]] && command -v virsh &>/dev/null; then
    existing_vols="$(virsh -c qemu:///system vol-list --pool default 2>/dev/null | awk 'NR>2 {print $1}')"
    stray_vols=()
    for name in "${NODES[@]}"; do
        for vol in "vagrant_${name}.img" "vagrant_${name}-vdb.qcow2"; do
            grep -qx "$vol" <<<"$existing_vols" && stray_vols+=("$vol")
        done
    done
    if [[ ${#stray_vols[@]} -gt 0 ]]; then
        warn "vagrant destroy left disk volumes behind in libvirt's 'default' pool:"
        for vol in "${stray_vols[@]}"; do
            if virsh -c qemu:///system vol-delete --pool default "$vol" &>/dev/null; then
                log "  removed $vol"
            else
                warn "  could not remove $vol — by hand: virsh -c qemu:///system vol-delete --pool default $vol"
            fi
        done
    fi
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
