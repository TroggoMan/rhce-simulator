#!/bin/bash
# Tears down everything rhce-simulator built: the Docker lab, the VM lab,
# and a quickstart container (scripts/quickstart-container.sh), each with
# its own confirmation. Doesn't touch your practice workdir or tracked
# history unless you say so, and doesn't delete this repo clone at all —
# that's the one step left for you to do by hand, printed at the end.
#
#   ./scripts/uninstall.sh          # asks before each step
#   ./scripts/uninstall.sh --yes    # don't ask, tear down everything found
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKDIR="${RHCE_SIM_WORKDIR:-$HOME/ansible}"
QUICKSTART_DIR="${RHCE_QUICKSTART_DIR:-/opt/docker-containers/rhce-control}"

ASSUME_YES=0
[[ "${1:-}" =~ ^(-y|--yes)$ ]] && ASSUME_YES=1

log()  { printf '\033[36m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[33m!!\033[0m %s\n' "$1"; }

confirm() {
    [[ "$ASSUME_YES" -eq 1 ]] && return 0
    read -r -p "$1 [Y/n] " reply
    [[ -z "$reply" || "$reply" =~ ^[Yy] ]]
}

found=0

# --- Docker lab --------------------------------------------------------
if command -v docker &>/dev/null \
   && docker compose -f "$REPO_DIR/docker/docker-compose.yml" ps -a -q 2>/dev/null | grep -q .; then
    found=1
    if confirm "Remove the Docker lab (containers + volumes)?"; then
        docker compose -f "$REPO_DIR/docker/docker-compose.yml" down -v
        log "Docker lab removed."
    fi
fi

# --- VM lab --------------------------------------------------------------
if command -v vagrant &>/dev/null && [[ -f "$REPO_DIR/vagrant/Vagrantfile" ]] \
   && VAGRANT_CWD="$REPO_DIR/vagrant" vagrant status 2>/dev/null \
        | grep -qE '^\S+\s+(running|poweroff|saved)\b'; then
    found=1
    if confirm "Destroy the VM lab (deletes the VMs and their disks)?"; then
        "$SCRIPT_DIR/vm-lab-teardown.sh" --destroy || warn "VM lab teardown reported a problem — check 'vagrant status' in vagrant/"
    fi
fi

# --- quickstart container -------------------------------------------------
if command -v docker &>/dev/null && [[ -f "$QUICKSTART_DIR/docker-compose.yml" ]]; then
    found=1
    if confirm "Remove the quickstart container at $QUICKSTART_DIR?"; then
        docker compose -f "$QUICKSTART_DIR/docker-compose.yml" down -v
        sudo rm -rf "$QUICKSTART_DIR"
        log "Quickstart container removed."
    fi
fi

# --- your practice workdir ------------------------------------------------
if [[ -d "$WORKDIR" ]] && find "$WORKDIR" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
    found=1
    warn "$WORKDIR has your playbooks/inventory in it — kept by default."
    if confirm "Delete it too? (a real delete, not an archive)"; then
        rm -rf "$WORKDIR"
        log "$WORKDIR removed."
    fi
fi

[[ "$found" -eq 0 ]] && log "Nothing found to remove."

echo
echo "Left in place: this repo clone, and your tracked practice history"
echo "(python3 rhce_simulator.py --reset-progress wipes just that)."
echo "Last step, once you're done with the simulator entirely:"
echo "    rm -rf $REPO_DIR"
