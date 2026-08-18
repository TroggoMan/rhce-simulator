#!/bin/bash
# Stands up a persistent, isolated Rocky Linux 10 container to run the
# simulator from, with its own non-root "student" user (passwordless
# sudo) instead of the image's default root — you never work as root
# directly on the real exam either.
#
# No repo checkout needed first — this is a single, standalone file:
#   curl -fsSL https://raw.githubusercontent.com/TroggoMan/rhce-simulator/master/scripts/quickstart-container.sh | bash
#
# The simulator itself is NOT installed here. From inside the container,
# git clone the repo and run ./scripts/bootstrap.sh --lab none exactly like
# any other host — see the README's Install section. This script only gets
# you the container to do that from; it has no /dev/kvm and no Docker
# daemon of its own, so it can't build either lab itself. Build one
# separately on your HOST, then connect this container to it.
set -euo pipefail

DIR="${RHCE_QUICKSTART_DIR:-/opt/docker-containers/rhce-control}"
IMAGE="${RHCE_QUICKSTART_IMAGE:-rockylinux/rockylinux:10}"

log()  { printf '\033[36m==>\033[0m %s\n' "$1"; }
die()  { printf '\033[31mERROR:\033[0m %s\n' "$1" >&2; exit 1; }

command -v docker &>/dev/null || die "Docker not found — install it first."
docker compose version &>/dev/null || die "'docker compose' plugin not available."

if [[ ! -d "$DIR" ]]; then
    log "Creating $DIR"
    sudo mkdir -p "$DIR"
    sudo chown "$(id -u):$(id -g)" "$DIR"
fi

if [[ ! -f "$DIR/docker-compose.yml" ]]; then
    log "Writing $DIR/docker-compose.yml"
    cat > "$DIR/docker-compose.yml" <<EOF
services:
  control:
    image: ${IMAGE}
    hostname: control
    command: sleep infinity
    working_dir: /home/student
    volumes:
      - control-home:/home/student
volumes:
  control-home:
EOF
fi

log "Starting the container..."
docker compose -f "$DIR/docker-compose.yml" up -d

log "Ensuring the 'student' user exists (passwordless sudo)..."
# -T (no pseudo-TTY) plus stdin redirected to /dev/null: this runs
# non-interactively (it's the scripted setup step, not the shell you land
# in), and this script is meant to be run as `curl | bash` — without both,
# exec either refuses outright ("cannot attach stdin to a TTY-enabled
# container") or, worse, silently attaches to the REST OF THIS SCRIPT's own
# piped stdin and consumes it, so everything after this call never runs.
docker compose -f "$DIR/docker-compose.yml" exec -T -u root control bash -c '
    command -v sudo &>/dev/null || dnf install -y sudo \
        || { echo "!! sudo not installed and dnf unavailable — install it" \
                  "yourself for a non-dnf image (RHCE_QUICKSTART_IMAGE)" >&2; exit 1; }
    id student &>/dev/null || useradd -m -s /bin/bash student
    mkdir -p /etc/sudoers.d
    echo "student ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/student
    chmod 0440 /etc/sudoers.d/student
    # The home volume mounts as an empty dir owned by root BEFORE useradd
    # ever runs, so -m sees it as "already exists" and leaves ownership
    # alone — fix it explicitly rather than relying on useradd to.
    chown -R student:student /home/student
' < /dev/null

echo
echo "Ready:"
echo "    docker compose -f $DIR/docker-compose.yml exec -u student control bash"
echo
echo "From there, same as any host — EXCEPT the lab: this container has no"
echo "/dev/kvm and no Docker daemon of its own, so it can't build either lab"
echo "itself. Pass --lab none and build a lab separately on your HOST, then"
echo "connect this container to it (see the README's Install section):"
echo "    sudo dnf install -y git      # match this to \$IMAGE if you changed it"
echo "    git clone https://github.com/TroggoMan/rhce-simulator.git"
echo "    cd rhce-simulator && ./scripts/bootstrap.sh --lab none"
echo
echo "Stop/remove it later:"
echo "    docker compose -f $DIR/docker-compose.yml down       # remove, keep the volume"
echo "    docker compose -f $DIR/docker-compose.yml down -v    # remove everything"
