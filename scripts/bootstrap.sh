#!/bin/bash
# One-step setup for rhce-simulator.
#
# Detects your OS and package manager, installs everything needed, configures
# services and group membership, then stands up a lab — nodes reachable with
# EXAM-STYLE bootstrap access only (root/password), no inventory written for
# you — so a fresh machine goes from "git clone" to "practising" in a single
# command. Building your own inventory/ansible.cfg/automation user from that
# bootstrap access is your actual first task; see the lab's own printed
# summary or `rhce_simulator.py --learn` (Configuring managed nodes).
#
#   ./scripts/bootstrap.sh                # pick a lab interactively
#   ./scripts/bootstrap.sh --lab vm       # QEMU/KVM VMs (grades SELinux)
#   ./scripts/bootstrap.sh --lab docker   # containers (faster, no SELinux)
#   ./scripts/bootstrap.sh --dry-run      # show what it WOULD do, change nothing
#   ./scripts/bootstrap.sh --yes          # don't prompt (CI / unattended)
#
# Supported: Arch (pacman), Debian/Ubuntu (apt), Fedora/RHEL/Rocky/Alma
# (dnf), openSUSE (zypper), macOS (brew), Windows via WSL2.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

LAB=""            # vm | docker | none
ASSUME_YES=0
DRY_RUN=0

C_INFO=$'\033[36m'; C_WARN=$'\033[33m'; C_ERR=$'\033[31m'
C_OK=$'\033[32m';   C_BOLD=$'\033[1m';  C_OFF=$'\033[0m'

log()  { printf '%s==>%s %s\n' "$C_INFO" "$C_OFF" "$1"; }
ok()   { printf '%s ok %s %s\n' "$C_OK" "$C_OFF" "$1"; }
warn() { printf '%s !! %s %s\n' "$C_WARN" "$C_OFF" "$1"; }
die()  { printf '%sERROR:%s %s\n' "$C_ERR" "$C_OFF" "$1" >&2; exit 1; }
step() { printf '\n%s%s%s\n' "$C_BOLD" "$1" "$C_OFF"; }

usage() { sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --lab)     LAB="${2:-}"; shift 2 ;;
        --lab=*)   LAB="${1#*=}"; shift ;;
        --yes|-y)  ASSUME_YES=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help) usage ;;
        *) die "unknown option: $1 (try --help)" ;;
    esac
done
[[ -z "$LAB" || "$LAB" =~ ^(vm|docker|none)$ ]] || die "--lab must be vm, docker or none"

confirm() {
    [[ "$ASSUME_YES" -eq 1 ]] && return 0
    read -r -p "$1 [Y/n] " reply </dev/tty || return 1
    [[ -z "$reply" || "$reply" =~ ^[Yy] ]]
}

# Every state-changing command goes through this, so --dry-run is honest:
# nothing mutates unless it is routed here.
run() {
    if [[ "$DRY_RUN" -eq 1 ]]; then
        printf '   %s[dry-run]%s %s\n' "$C_WARN" "$C_OFF" "$*"
        return 0
    fi
    "$@"
}

have() { command -v "$1" >/dev/null 2>&1; }

# ---------------------------------------------------------------------------
# 1. Detect platform
# ---------------------------------------------------------------------------

step "1. Detecting platform"

OS=""; FAMILY=""; PM=""; SUDO=""; IS_WSL=0
[[ $EUID -ne 0 ]] && SUDO="sudo"

if grep -qi microsoft /proc/version 2>/dev/null; then IS_WSL=1; fi

case "$(uname -s)" in
    Darwin)
        OS="macos"; FAMILY="macos"
        have brew || die \
"Homebrew is required on macOS. Install it first:
  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        PM="brew"; SUDO=""
        ;;
    Linux)
        OS="linux"
        if   have pacman; then PM="pacman"; FAMILY="arch"
        elif have apt-get; then PM="apt";   FAMILY="debian"
        elif have dnf;    then PM="dnf";    FAMILY="rhel"
        elif have zypper; then PM="zypper"; FAMILY="suse"
        else die "No supported package manager found (pacman/apt/dnf/zypper)."
        fi
        ;;
    MINGW*|MSYS*|CYGWIN*)
        die \
"Native Windows shells can't run this — Ansible has no Windows control node.
Install WSL2, then run this script from inside your WSL distribution:
  wsl --install -d Ubuntu"
        ;;
    *) die "Unsupported OS: $(uname -s)" ;;
esac

DISTRO_NAME="$(. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME:-}" || sw_vers -productName 2>/dev/null || echo "$OS")"
ok "$DISTRO_NAME  (package manager: $PM)"
[[ "$IS_WSL" -eq 1 ]] && warn "Running under WSL2 — see the VM-lab note below."

# ---------------------------------------------------------------------------
# 2. Choose a lab
# ---------------------------------------------------------------------------

step "2. Choosing a lab"

KVM_OK=0
[[ -e /dev/kvm ]] && KVM_OK=1

if [[ -z "$LAB" ]]; then
    echo "  vm     - QEMU/KVM virtual machines. Grades everything, including"
    echo "           SELinux, the network role and the raw-disk task."
    echo "  docker - Containers. Faster and lighter, but CANNOT grade SELinux"
    echo "           (host-kernel feature; no container can)."
    echo "  none   - Just install tooling; I'll set up nodes myself."
    echo
    default="docker"
    [[ "$OS" == "linux" && "$KVM_OK" -eq 1 && "$IS_WSL" -eq 0 ]] && default="vm"
    if [[ "$ASSUME_YES" -eq 1 ]]; then
        LAB="$default"
    else
        read -r -p "Which lab? [$default] " LAB </dev/tty || LAB="$default"
        LAB="${LAB:-$default}"
    fi
fi
[[ "$LAB" =~ ^(vm|docker|none)$ ]] || die "invalid lab: $LAB"
ok "lab: $LAB"

if [[ "$LAB" == "vm" ]]; then
    if [[ "$OS" == "linux" && "$KVM_OK" -eq 0 ]]; then
        warn "/dev/kvm is missing — VMs will run fully emulated and be very slow."
        warn "Enable virtualisation (VT-x/AMD-V) in firmware, or use --lab docker."
        confirm "Continue anyway?" || exit 1
    fi
    if [[ "$IS_WSL" -eq 1 ]]; then
        warn "Vagrant inside WSL2 cannot drive VirtualBox/Hyper-V on the Windows"
        warn "host without extra configuration. The Docker lab is the reliable"
        warn "path on Windows; see the README's Platform support section."
        confirm "Continue with the VM lab anyway?" || exit 1
    fi
    if [[ "$OS" == "macos" && "$(uname -m)" == "arm64" ]]; then
        warn "Apple Silicon: VirtualBox arm64 support is poor and Rocky ships no"
        warn "VMware Vagrant box, so there is no clean scripted VM path here."
        warn "Recommend --lab docker, then a UTM/Parallels VM for SELinux work."
        confirm "Continue with the VM lab anyway?" || exit 1
    fi
fi

# ---------------------------------------------------------------------------
# 3. Work out what to install
# ---------------------------------------------------------------------------

step "3. Resolving packages"

PKGS=()          # installed via the system package manager
NEED_VAGRANT=0   # handled separately: not packaged consistently
POST=()          # human-readable post-install actions, executed in step 5

# Core tooling every platform needs.
case "$FAMILY" in
    arch)   PKGS+=(git python ansible-core python-pipx) ;;
    debian) PKGS+=(git python3 python3-pip ansible-core pipx) ;;
    rhel)   PKGS+=(git python3 python3-pip ansible-core pipx) ;;
    suse)   PKGS+=(git python3 ansible python3-pipx) ;;
    macos)  PKGS+=(git python ansible pipx) ;;
esac

if [[ "$LAB" == "vm" ]]; then
    NEED_VAGRANT=1
    case "$FAMILY" in
        arch)   PKGS+=(libvirt qemu-desktop dnsmasq virt-install) ;;
        debian) PKGS+=(qemu-system-x86 libvirt-daemon-system libvirt-clients
                       virtinst dnsmasq-base ruby-dev libvirt-dev gcc make) ;;
        rhel)   PKGS+=(qemu-kvm libvirt virt-install libvirt-devel gcc make) ;;
        suse)   PKGS+=(qemu-kvm libvirt virt-install libvirt-devel gcc make) ;;
        macos)  PKGS+=() ;;   # VirtualBox cask handled with Vagrant below
    esac
fi

if [[ "$LAB" == "docker" ]]; then
    case "$FAMILY" in
        arch)   PKGS+=(docker docker-compose) ;;
        debian) PKGS+=(docker.io docker-compose-v2) ;;
        rhel)   PKGS+=(docker podman-docker docker-compose) ;;
        suse)   PKGS+=(docker docker-compose) ;;
        macos)  PKGS+=() ;;   # Docker Desktop cask below
    esac
fi

printf '   system packages: %s\n' "${PKGS[*]:-(none)}"
[[ "$NEED_VAGRANT" -eq 1 ]] && printf '   plus: vagrant + libvirt/virtualbox provider\n'

# ---------------------------------------------------------------------------
# 4. Install
# ---------------------------------------------------------------------------

step "4. Installing"

if [[ ${#PKGS[@]} -gt 0 ]]; then
    echo "About to install: ${PKGS[*]}"
    confirm "Proceed?" || die "aborted by user"
    case "$PM" in
        pacman) run $SUDO pacman -S --needed --noconfirm "${PKGS[@]}" ;;
        apt)    run $SUDO apt-get update -qq
                run $SUDO apt-get install -y "${PKGS[@]}" ;;
        dnf)    run $SUDO dnf install -y "${PKGS[@]}" ;;
        zypper) run $SUDO zypper --non-interactive install "${PKGS[@]}" ;;
        brew)   run brew install "${PKGS[@]}" ;;
    esac
    ok "system packages installed"
fi

# --- Vagrant + provider ----------------------------------------------------
if [[ "$NEED_VAGRANT" -eq 1 ]]; then
    if have vagrant; then
        ok "vagrant already present ($(vagrant --version 2>/dev/null || echo '?'))"
    else
        case "$FAMILY" in
            arch)
                # Vagrant was dropped from the Arch repos; it lives in the AUR.
                helper=""
                for h in paru yay pikaur trizen; do have "$h" && { helper="$h"; break; }; done
                if [[ -n "$helper" ]]; then
                    log "Installing vagrant from the AUR via $helper"
                    run "$helper" -S --needed --noconfirm vagrant
                else
                    die "Vagrant is not in the Arch repos and no AUR helper (paru/yay)
was found. Install one, or grab Vagrant from
https://developer.hashicorp.com/vagrant/downloads, then re-run."
                fi
                ;;
            debian)
                log "Adding HashiCorp's apt repository (Debian/Ubuntu ship an old vagrant)"
                run bash -c 'curl -fsSL https://apt.releases.hashicorp.com/gpg \
                    | gpg --dearmor | sudo tee /usr/share/keyrings/hashicorp.gpg >/dev/null'
                run bash -c 'echo "deb [signed-by=/usr/share/keyrings/hashicorp.gpg] \
https://apt.releases.hashicorp.com $(lsb_release -cs) main" \
                    | sudo tee /etc/apt/sources.list.d/hashicorp.list >/dev/null'
                run $SUDO apt-get update -qq
                run $SUDO apt-get install -y vagrant
                ;;
            rhel)   run $SUDO dnf install -y vagrant ;;
            suse)   run $SUDO zypper --non-interactive install vagrant ;;
            macos)  run brew install --cask vagrant virtualbox ;;
        esac
    fi

    # Provider plugin (Linux only — macOS uses VirtualBox, which needs none).
    if [[ "$OS" == "linux" ]]; then
        if vagrant plugin list 2>/dev/null | grep -q vagrant-libvirt; then
            ok "vagrant-libvirt plugin already installed"
        else
            log "Installing the vagrant-libvirt plugin"
            if ! run vagrant plugin install vagrant-libvirt; then
                warn "Plain install failed — retrying with the build flags that"
                warn "Vagrant's bundled Ruby usually needs."
                run env CONFIGURE_ARGS='with-ldflags=-L/opt/vagrant/embedded/lib with-libvirt-include=/usr/include/libvirt with-libvirt-lib=/usr/lib' \
                    vagrant plugin install vagrant-libvirt \
                    || die "vagrant-libvirt failed to build. See
https://vagrant-libvirt.github.io/vagrant-libvirt/installation.html
or re-run with --lab docker."
            fi
        fi
        POST+=("enable libvirt: $SUDO systemctl enable --now libvirtd.socket")
        POST+=("join the libvirt group: $SUDO usermod -aG libvirt $USER")
    fi
fi

# --- Docker ----------------------------------------------------------------
if [[ "$LAB" == "docker" ]]; then
    if [[ "$OS" == "macos" ]]; then
        have docker || run brew install --cask docker
        warn "Start Docker Desktop once before continuing."
    else
        POST+=("enable docker: $SUDO systemctl enable --now docker")
        POST+=("join the docker group: $SUDO usermod -aG docker $USER")
    fi
fi

# --- Ansible collections ---------------------------------------------------
# ansible-core deliberately ships no collections, but most of the task
# catalog needs them: ansible.posix for firewalld/mount/seboolean/
# authorized_key, community.general for lvol/lvg/parted/seport/sefcontext/
# archive. Without these a candidate's perfectly correct playbook fails with
# "couldn't resolve module/action", which reads like their mistake.
if have ansible-galaxy; then
    if ansible-galaxy collection list 2>/dev/null | grep -q "ansible.posix"; then
        ok "ansible.posix / community.general already installed"
    else
        log "Installing the collections the task catalog depends on"
        run ansible-galaxy collection install ansible.posix community.general \
            || warn "collection install failed — run it yourself before practising:
      ansible-galaxy collection install ansible.posix community.general"
    fi
else
    warn "ansible-galaxy not found; install collections later with:"
    warn "  ansible-galaxy collection install ansible.posix community.general"
fi

# --- ansible-navigator (optional; not packaged consistently) ---------------
if have ansible-navigator; then
    ok "ansible-navigator already present"
else
    if have pipx; then
        log "Installing ansible-navigator via pipx"
        run pipx install ansible-navigator || warn "ansible-navigator install failed — optional, continuing"
    else
        warn "ansible-navigator not installed (pipx not found)."
        warn "It's optional: only the navigator tasks need it, and they degrade"
        warn "gracefully. Install later with:  pipx install ansible-navigator"
    fi
fi

# ---------------------------------------------------------------------------
# 5. Services and groups
# ---------------------------------------------------------------------------

if [[ ${#POST[@]} -gt 0 ]]; then
    step "5. Services and group membership"
    for action in "${POST[@]}"; do
        desc="${action%%:*}"; cmd="${action#*: }"
        log "$desc"
        run $cmd || warn "failed (may already be done): $cmd"
    done
    NEWGRP=""
    [[ "$LAB" == "vm"     && "$OS" == "linux" ]] && NEWGRP="libvirt"
    [[ "$LAB" == "docker" && "$OS" == "linux" ]] && NEWGRP="docker"
fi

# ---------------------------------------------------------------------------
# 6. Build the lab
# ---------------------------------------------------------------------------

step "6. Building the lab"

if [[ "$LAB" == "none" ]]; then
    ok "Tooling installed. Set RHCE_SIM_NODES to your own machines when ready."
elif [[ "$DRY_RUN" -eq 1 ]]; then
    printf '   %s[dry-run]%s would run scripts/%s\n' "$C_WARN" "$C_OFF" \
        "$([[ $LAB == vm ]] && echo vm-lab-setup.sh || echo lab-setup.sh)"
else
    # Group changes don't apply to the current shell until re-login, which
    # would make the lab script fail on a permission error. Detect that and
    # tell the user plainly rather than dying halfway through a build.
    if [[ -n "${NEWGRP:-}" ]] && ! id -nG | tr ' ' '\n' | grep -qx "$NEWGRP"; then
        warn "You were added to the '$NEWGRP' group, but this shell doesn't have it yet."
        echo
        echo "  Run these two commands to finish:"
        echo "      newgrp $NEWGRP"
        echo "      $REPO_DIR/scripts/$([[ $LAB == vm ]] && echo vm-lab-setup.sh || echo lab-setup.sh)"
        echo
        exit 0
    fi
    if [[ "$LAB" == "vm" ]]; then
        "$REPO_DIR/scripts/vm-lab-setup.sh"
    else
        "$REPO_DIR/scripts/lab-setup.sh"
    fi
fi

# ---------------------------------------------------------------------------
# 7. Done
# ---------------------------------------------------------------------------

step "Done"
if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "Dry run only — nothing was installed or changed."
else
    echo "Nodes are up with bootstrap access only (see the root password/SSH"
    echo "details printed above) — no inventory yet. That's task 1:"
    echo "    cd $REPO_DIR"
    echo "    python3 rhce_simulator.py --learn     # Configuring managed nodes"
    echo "    python3 rhce_simulator.py --practice managed_nodes"
    echo "Once  ansible all -m ping  works against your OWN inventory:"
    [[ "$LAB" == "vm" ]]     && echo "    export RHCE_SIM_NODES=\"morty,summer,jerry\""
    [[ "$LAB" == "docker" ]] && echo "    export RHCE_SIM_NODES=\"morty,summer,jerry,beth,rick\""
    echo "    python3 rhce_simulator.py --quick     # 5 tasks"
fi
