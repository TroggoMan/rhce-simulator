#!/bin/bash
# Builds/starts, stops, destroys or reports on the optional Rocky Linux 10
# "control" container — a bare, self-contained practice control node. It
# does NOT come with the simulator's toolchain preinstalled: once you're in,
# git clone this repo and run ./scripts/bootstrap.sh exactly as the README
# has you do on a real host — same install path either way. See
# docker/Dockerfile.control for what IS preinstalled (just enough to get in,
# clone, and reach managed nodes) and why.
#
# Entirely optional and decoupled from whichever (if any) managed-node lab
# you're running — this is the only script that should build/start/stop the
# 'control' service in docker-compose.yml.
#
#   ./scripts/control-setup.sh            # build+start, bridge network
#                                          # (resolves the Docker lab's own
#                                          # nodes by hostname if it's up)
#   ./scripts/control-setup.sh --vm       # build+start, host networking
#                                          # (pairs with the VM lab instead)
#   ./scripts/control-setup.sh --status   # show whether it's running
#   ./scripts/control-setup.sh --stop     # stop it, keep it
#   ./scripts/control-setup.sh --destroy  # remove it entirely
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$SCRIPT_DIR/../docker"

log()  { printf '\033[36m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[33m!!\033[0m %s\n' "$1"; }
die()  { printf '\033[31mERROR:\033[0m %s\n' "$1" >&2; exit 1; }

ACTION=up
VM=0
for arg in "$@"; do
    case "$arg" in
        --vm)       VM=1 ;;
        --status)   ACTION=status ;;
        --stop)     ACTION=stop ;;
        --destroy)  ACTION=destroy ;;
        -h|--help)  sed -n '2,20p' "$0" | sed 's/^# \?//'; exit 0 ;;
        *)          die "unknown option '$arg' (try --help)" ;;
    esac
done

present() {
    command -v docker &>/dev/null && \
        docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx control
}

# stop/destroy/status act on the container by name directly — no need to
# resolve compose files for these, and it keeps them from ever touching the
# managed-node services docker-compose.yml also defines. They also tolerate
# a missing Docker (report/no-op rather than die) so callers like
# vm-lab-teardown.sh can invoke them unconditionally as best-effort cleanup.
case "$ACTION" in
    status)
        if present; then
            docker ps -a --filter name='^control$' --format 'control   {{.Status}}'
        else
            echo "control is not present."
        fi
        exit 0
        ;;
    stop)
        if present; then
            log "Stopping the control container (kept — bring it back with $0)."
            docker stop control &>/dev/null \
                || warn "Could not stop it — by hand: docker stop control"
        else
            warn "control is not present — nothing to stop."
        fi
        exit 0
        ;;
    destroy)
        if present; then
            log "Removing the control container and its home volume (your clone, progress and SSH keys go with it)."
            docker rm -f control &>/dev/null \
                || warn "Could not remove it — by hand: docker rm -f control"
        else
            warn "control is not present — nothing to destroy."
        fi
        docker volume rm rhce-lab_control-home &>/dev/null || true
        exit 0
        ;;
esac

command -v docker &>/dev/null || die "Docker not found on PATH."
docker compose version &>/dev/null || die "'docker compose' plugin not available."

COMPOSE_FILES=(-f "$DOCKER_DIR/docker-compose.yml")
if [[ "$VM" -eq 1 ]]; then
    COMPOSE_FILES+=(-f "$DOCKER_DIR/docker-compose.control-vm.yml")
fi

log "Building and starting the control container..."
RHCE_LAB_UID="$(id -u)" RHCE_LAB_GID="$(id -g)" \
    docker compose "${COMPOSE_FILES[@]}" up -d --build control

echo
echo "Control node is up:"
echo "    docker exec -it control bash"
echo "It's bare Rocky Linux 10 — get the simulator running exactly like you"
echo "would on any other machine:"
echo "    git clone https://github.com/TroggoMan/rhce-simulator.git"
echo "    cd rhce-simulator"
echo "    ./scripts/bootstrap.sh --lab none   # nodes are handled separately"
echo "Your whole \$HOME persists across stop/start in a named volume, so"
echo "the clone, your progress and your SSH keys are all still there next"
echo "time — even though nothing is bind-mounted from the host."
if [[ "$VM" -eq 1 ]]; then
    echo
    echo "Host networking is in use so this reaches the VM lab's"
    echo "libvirt/VirtualBox addresses — Docker's own managed nodes (if any"
    echo "are running) will NOT resolve by hostname from here, unlike the"
    echo "default (non --vm) mode. Use the VM IPs from 'vagrant ssh-config"
    echo "<node>' directly in your inventory's ansible_host=."
else
    echo
    echo "Managed nodes are reachable as plain hostnames on port 22 (kirk,"
    echo "spock, mccoy, scotty) if the Docker lab (scripts/lab-setup.sh)"
    echo "is up — no 127.0.0.1:220x needed."
fi
echo
echo "ansible-navigator's execution-environment feature needs nested"
echo "containers, which don't run inside this one — pass"
echo "--execution-environment false (or --ee false) to any navigator command"
echo "run from control. ansible-navigator doc works fine either way."
