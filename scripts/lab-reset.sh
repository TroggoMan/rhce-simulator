#!/bin/bash
# Fast state reset for whichever lab is active — puts the managed nodes
# back to a clean slate WITHOUT the multi-minute rebuild/reprovision that
# vm-lab-teardown.sh + vm-lab-setup.sh (or lab-setup.sh) would cost you.
#
# Practice sessions accumulate state on the managed nodes (users, LVM,
# cron jobs, vault files, SELinux labels...) that a real exam retake would
# never carry over. This is the "start this task fresh" button.
#
#   ./scripts/lab-reset.sh            # reset whichever lab is currently up
#   ./scripts/lab-reset.sh --docker   # force docker-lab reset
#   ./scripts/lab-reset.sh --vm       # force VM-lab reset (restores a snapshot)
#   ./scripts/lab-reset.sh --vm --save-snapshot   # (re)create the VM lab's
#                                                    baseline snapshot from
#                                                    its CURRENT state
#
# Docker lab: force-recreates every container from its already-built image
# (no rebuild needed) — a few seconds. Bootstrap access (root/password) is
# baked into the image itself, so a fresh container already has it; there's
# nothing to re-inject the way there was when the image baked in an SSH key.
#
# VM lab: restores a Vagrant snapshot named "clean". The first time you
# ever use the VM lab, take that snapshot once (right after vm-lab-setup.sh
# finishes and before you touch anything):
#   ./scripts/lab-reset.sh --vm --save-snapshot
# Every reset after that is a snapshot restore — seconds, not minutes,
# and doesn't need scripts/vm-lab-setup.sh to run again.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCKER_DIR="$REPO_DIR/docker"
VAGRANT_DIR="$REPO_DIR/vagrant"
NODES_DOCKER=(morty summer jerry beth rick)
NODES_VM=(morty summer jerry)
ROOT_PASSWORD="${RHCE_LAB_ROOT_PASSWORD:-rhce-lab}"
SNAPSHOT_NAME=clean
DOCKER_BASE_PORT=2201

# A recreated container generates brand-new SSH host keys on first boot,
# but it reuses the same 127.0.0.1:220x address — so every stale
# known_hosts entry now looks exactly like a man-in-the-middle attack and
# ssh refuses to connect at all. host_key_checking = False does NOT save
# you here: that only skips prompting for an UNKNOWN key; a CHANGED one is
# a hard failure by design. Nothing else in the lab can work until these
# are gone, so drop them as part of the reset rather than leaving the
# candidate to decode "REMOTE HOST IDENTIFICATION HAS CHANGED" themselves.
forget_docker_host_keys() {
    command -v ssh-keygen &>/dev/null || return 0
    [[ -f "$HOME/.ssh/known_hosts" ]] || return 0
    local failed=0 i
    for i in "${!NODES_DOCKER[@]}"; do
        ssh-keygen -R "[127.0.0.1]:$((DOCKER_BASE_PORT + i))" &>/dev/null || failed=1
    done
    # ssh-keygen -R refuses to rewrite the WHOLE file if ANY line in it is
    # malformed (a stray blank/CR-only line is enough), so this can fail
    # while looking like it worked. Say so — silently leaving stale keys
    # behind means every later connection dies with a scary MITM banner.
    if [[ "$failed" -eq 1 ]]; then
        warn "Couldn't clear old host keys from ~/.ssh/known_hosts."
        warn "ssh-keygen refuses to rewrite that file if any line in it is"
        warn "malformed; check it with: ssh-keygen -R '[127.0.0.1]:$DOCKER_BASE_PORT'"
        warn "Until it's fixed, connections to the lab will fail with"
        warn "'REMOTE HOST IDENTIFICATION HAS CHANGED'."
    fi
}

log()  { printf '\033[36m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[33m!!\033[0m %s\n' "$1"; }
die()  { printf '\033[31mERROR:\033[0m %s\n' "$1" >&2; exit 1; }

LAB=""
SAVE_SNAPSHOT=0
for arg in "$@"; do
    case "$arg" in
        --docker)        LAB=docker ;;
        --vm)             LAB=vm ;;
        --save-snapshot)  SAVE_SNAPSHOT=1 ;;
        -h|--help)        sed -n '2,20p' "$0" | sed 's/^# \?//'; exit 0 ;;
        *)                die "unknown option '$arg' (try --help)" ;;
    esac
done

# ---------------------------------------------------------------------------
# Auto-detect which lab is running, if the caller didn't say
# ---------------------------------------------------------------------------

if [[ -z "$LAB" ]]; then
    if docker compose -f "$DOCKER_DIR/docker-compose.yml" ps -q 2>/dev/null | grep -q .; then
        LAB=docker
    elif [[ -f "$VAGRANT_DIR/Vagrantfile" ]] && \
         VAGRANT_CWD="$VAGRANT_DIR" vagrant status 2>/dev/null | grep -q running; then
        LAB=vm
    else
        die "No running lab detected. Start one first with scripts/lab-setup.sh"\
" (Docker) or scripts/vm-lab-setup.sh (VMs), or pass --docker/--vm explicitly."
    fi
fi

# ---------------------------------------------------------------------------
# Docker lab: force-recreate every container from its existing image
# ---------------------------------------------------------------------------

reset_docker() {
    command -v docker &>/dev/null || die "Docker not found on PATH."

    log "Force-recreating the Docker lab containers (${NODES_DOCKER[*]})..."
    # Same pass-through as lab-setup.sh: the control node's user has to
    # keep matching yours, and the compose file needs an absolute workdir
    # for its bind mount.
    RHCE_LAB_ROOT_PASSWORD="$ROOT_PASSWORD" \
    RHCE_LAB_UID="$(id -u)" RHCE_LAB_GID="$(id -g)" \
    RHCE_SIM_WORKDIR="${RHCE_SIM_WORKDIR:-$HOME/ansible}" \
        docker compose -f "$DOCKER_DIR/docker-compose.yml" up -d --force-recreate

    log "Waiting for sshd in each container..."
    for name in "${NODES_DOCKER[@]}"; do
        for attempt in $(seq 1 30); do
            docker exec "$name" systemctl is-active sshd &>/dev/null && break
            [[ "$attempt" -eq 30 ]] && die "sshd never came up in $name"
            sleep 1
        done
    done

    log "Forgetting the old container host keys..."
    forget_docker_host_keys

    log "Docker lab reset — every node is back to bootstrap access only"
    log "(root / $ROOT_PASSWORD). Your own inventory/ansible.cfg/automation"
    log "user are gone with it — that's the whole point of a reset. Rebuild"
    log "them the same way you did the first time."
}

# ---------------------------------------------------------------------------
# VM lab: snapshot save/restore (Vagrant core feature, no plugin needed)
# ---------------------------------------------------------------------------

reset_vm() {
    command -v vagrant &>/dev/null || die "Vagrant not found on PATH."
    [[ -f "$VAGRANT_DIR/Vagrantfile" ]] || die "No Vagrantfile at $VAGRANT_DIR."
    export VAGRANT_CWD="$VAGRANT_DIR"
    run_vagrant() { vagrant "$@" 2>&1 | grep -v '^\[fog\]' || true; }

    if [[ "$SAVE_SNAPSHOT" -eq 1 ]]; then
        log "Saving the current VM state as the '$SNAPSHOT_NAME' baseline snapshot..."
        run_vagrant snapshot save --force "$SNAPSHOT_NAME"
        log "Baseline saved. Future 'lab-reset.sh --vm' runs restore this exact state."
        return
    fi

    log "Restoring the '$SNAPSHOT_NAME' snapshot on ${NODES_VM[*]}..."
    if ! run_vagrant snapshot list 2>/dev/null | grep -q "$SNAPSHOT_NAME"; then
        die "No '$SNAPSHOT_NAME' snapshot found. Create one first (once, on a"\
" freshly-provisioned lab, before you start practicing):
      $0 --vm --save-snapshot"
    fi
    run_vagrant snapshot restore "$SNAPSHOT_NAME"
    log "VM lab reset — every node is back to the '$SNAPSHOT_NAME' snapshot."
}

if [[ "$LAB" == "docker" ]]; then
    reset_docker
else
    reset_vm
fi
