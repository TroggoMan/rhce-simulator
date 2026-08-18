#!/bin/bash
# Archives (never silently deletes) and clears $RHCE_SIM_WORKDIR — your own
# ansible.cfg/inventory/playbooks — so you can start a fresh practice
# session without rebuilding a lab. Managed-node state is untouched (see
# lab-reset.sh for that); so is your tracked progress history, which lives
# in the simulator's own data dir, not here (see --reset-progress).
#
#   ./scripts/reset-workdir.sh          # archive + clear, asks first
#   ./scripts/reset-workdir.sh --yes    # don't ask
set -euo pipefail

WORKDIR="${RHCE_SIM_WORKDIR:-$HOME/ansible}"
ASSUME_YES=0
[[ "${1:-}" =~ ^(-y|--yes)$ ]] && ASSUME_YES=1

log()  { printf '\033[36m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[33m!!\033[0m %s\n' "$1"; }

confirm() {
    [[ "$ASSUME_YES" -eq 1 ]] && return 0
    read -r -p "$1 [Y/n] " reply
    [[ -z "$reply" || "$reply" =~ ^[Yy] ]]
}

if [[ -d "$WORKDIR" ]] && find "$WORKDIR" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
    warn "$WORKDIR already has content in it."
    if confirm "Archive it and start exam-blank?"; then
        stamp="$(date +%Y%m%d-%H%M%S)"
        archive="${WORKDIR%/}-archive-$stamp.tar.gz"
        log "Archiving to $archive"
        tar -czf "$archive" -C "$WORKDIR" .
        find "$WORKDIR" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
        log "Workdir cleared."
    else
        warn "Left as-is."
    fi
else
    mkdir -p "$WORKDIR"
    log "$WORKDIR is already exam-blank."
fi
