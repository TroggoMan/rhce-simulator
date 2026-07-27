# RHCE Exam Simulator

RHCE **EX294 (RHEL 10)** exam simulator — a command-line trainer for what
Red Hat now officially calls the *Red Hat Certified Advanced System
Administrator in Ansible Exam* (renamed from "RHCE exam" in a May 2026
certification-catalog restructure — same content/objectives, RHCE is now a
stacked title earned by passing it; kept "RHCE" in this project's name
since that's still what everyone searches for). Presents exam-style
Ansible automation tasks, then grades them the way the real exam does:
**by results, not methods** — it runs your playbooks against your own
inventory and inspects the state they produce on your managed nodes.

Sibling project to [rhcsa-simulator](https://github.com/TroggoMan/rhcsa-simulator)
(RHCSA EX200 v10), sharing its conventions: Python standard library only,
task auto-discovery, SQLite progress tracking.

Objectives and task content were audited against Red Hat's current
official EX294 page and current Ansible tooling docs on 2026-07-23, and
re-verified against Red Hat primary sources on 2026-07-27 — see
`config/exam_objectives.py` and `config/learn_content.py` for sourcing
notes, including which claims are Red Hat's own wording and which are
inference or community consensus.

## How grading works

Every task is validated in up to three layers:

1. **Artifacts** — the required files exist in your working directory and
   contain what was asked (static checks; always run).
2. **Execution** — the playbook passes `--syntax-check`, runs cleanly against
   *your* inventory with *your* `ansible.cfg`, and is **idempotent**
   (a second run must report `changed=0` — the exam's favorite trap).
3. **State** — ad-hoc queries against your managed nodes confirm the end
   state the playbook was supposed to produce.

## Install (one step)

```bash
git clone https://github.com/TroggoMan/rhce-simulator.git
cd rhce-simulator
./scripts/bootstrap.sh
```

That's it. `bootstrap.sh` detects your OS and package manager, installs
everything needed, configures services and group membership, builds a lab,
and writes your `inventory` and `ansible.cfg`. It asks before installing
anything and never installs silently.

```bash
./scripts/bootstrap.sh --lab vm       # QEMU/KVM VMs — grades everything, incl. SELinux
./scripts/bootstrap.sh --lab docker   # containers — faster/lighter, no SELinux
./scripts/bootstrap.sh --lab none     # just the tooling; I'll bring my own nodes
./scripts/bootstrap.sh --dry-run      # show exactly what it would do, change nothing
./scripts/bootstrap.sh --yes          # unattended
```

Run it with `--dry-run` first if you'd rather see the exact package-manager
commands before anything touches your system.

| Package manager | Platforms |
|---|---|
| `pacman` | Arch, CachyOS, Manjaro, EndeavourOS |
| `apt` | Debian, Ubuntu, Mint, Pop!_OS |
| `dnf` | Fedora, RHEL, Rocky, Alma, CentOS Stream |
| `zypper` | openSUSE, SLES |
| `brew` | macOS |

On Windows, run it inside WSL2 — Ansible has no native Windows control
node. See **Platform support**.

### What it installs

| What | Needed for | Notes |
|---|---|---|
| **Python 3.9+** | the simulator itself | Standard library only — nothing to `pip install`, no virtualenv needed to run it. |
| **ansible-core** | execution + node-state grading | Without it the simulator still grades your files statically; it just can't run your playbooks. |
| **ansible-navigator** | the navigator tasks | Installed via `pipx`. Optional — those tasks degrade gracefully without it. |
| **ansible.posix + community.general** | most of the catalog | ansible-core ships NO collections, but the tasks need `firewalld`, `mount`, `seboolean`, `lvol`, `parted`, `seport`, `sefcontext`, `archive`… |
| **git** | the source-control tasks | The lab "remote" is a local bare repo; no network or GitHub account needed. |
| **QEMU/KVM + libvirt + Vagrant** | the VM lab | `--lab vm` only. Lightweight and kernel-native on Linux — no VirtualBox kernel modules. |
| **Docker + compose** | the Docker lab | `--lab docker` only. |

You never need both Docker and QEMU — pick one lab.

### Doing it by hand instead

If you'd rather not run a script that installs things, everything it does
is in **Lab setup** below, and the individual lab builders
(`scripts/lab-setup.sh`, `scripts/vm-lab-setup.sh`) work standalone once
you have the tooling. The one step that's easy to miss is the collections —
`ansible-core` installs none, and without them most playbooks fail to
resolve their modules:

```bash
ansible-galaxy collection install ansible.posix community.general
```

## Quick start

```bash
python3 rhce_simulator.py --quick             # 5 random tasks
python3 rhce_simulator.py --exam              # full 4-hour-style exam (20 tasks)
python3 rhce_simulator.py --practice selinux  # drill one category
python3 rhce_simulator.py --list-tasks        # catalog overview
python3 rhce_simulator.py --learn             # browse domains -> topics -> real study content
python3 rhce_simulator.py --history           # past sessions & weak categories
```

Inside a session: type a task number to read it, do the work **in another
terminal**, then `v <n>` to validate it (`h <n>` for hints, `q` to finish).

`--learn` is interactive: pick a domain, pick a category inside it, and get
an actual concept explanation, real module syntax with working examples,
the mistakes that actually cost points, and exam tips — not just a list of
objective bullets. `[P]` from a topic screen jumps straight into practicing
that category.

## Lab setup

**This is the part that matters.** The simulator grades by running your
playbooks against real managed nodes, so it needs nodes.

`./scripts/bootstrap.sh` (above) does all of this for you including
installing the prerequisites — this section is the detail behind it, for
when you want to choose deliberately, rebuild a lab, or drive the
individual scripts yourself.

| | Docker lab | VM lab | Your own machines |
|---|---|---|---|
| Command | `./scripts/lab-setup.sh` | `./scripts/vm-lab-setup.sh` | manual |
| Nodes | 5 containers | 3 VMs | however many you have |
| Setup time | ~2 min | ~10 min (downloads a ~1GB box) | — |
| Disk/RAM cost | low | ~3GB RAM, ~15GB disk | — |
| **Grades SELinux tasks** | ❌ impossible | ✅ yes | ✅ if enforcing |
| **Grades the raw-disk task** | ❌ no spare disk | ✅ yes | ✅ if you attach one |
| **Grades the network role** | ❌ no NetworkManager | ✅ yes | ✅ yes |
| Everything else | ✅ | ✅ | ✅ |

Both scripts write an `inventory` and `ansible.cfg` into `$RHCE_SIM_WORKDIR`
and back up anything already there. Neither installs software without
asking first.

**Start with the Docker lab.** It covers the large majority of the catalog,
costs almost nothing, and tears down instantly. Add the VM lab when you
want to drill SELinux specifically — those tasks are the reason it exists.

### Option 1 — Docker lab (fastest, recommended first)

```bash
./scripts/lab-setup.sh
export RHCE_SIM_NODES="morty,summer,jerry,beth,rick"
python3 rhce_simulator.py --quick
```

Builds 5 systemd-enabled Rocky Linux 10 containers (`morty`, `summer`,
`jerry`, `beth`, `rick`) on `127.0.0.1:2201`-`2205`. Tear down with
`docker compose -f docker/docker-compose.yml down -v`.

**What it cannot do:** SELinux. That is a host-kernel feature — containers
share the host's kernel and get no `selinuxfs` of their own, so *no*
container can enforce SELinux regardless of how it's configured. The
simulator handles this honestly instead of silently: SELinux tasks still
grade your playbook's content, then mark the execution and node-state
checks **skipped** — never failed — so a correct answer is never penalised
for a lab that can't observe it. Same treatment for the `network`
system-role task (needs NetworkManager) and the raw-disk storage task
(needs a spare disk). Firewalld works, but is less faithful than a real
host's netfilter stack.

### Option 2 — VM lab (needed for SELinux)

```bash
./scripts/vm-lab-setup.sh
export RHCE_SIM_NODES="morty,summer,jerry"
python3 rhce_simulator.py --practice selinux
```

Three Rocky Linux 10 VMs via Vagrant, **SELinux enforcing**, with a blank
10G disk attached to `jerry` for the partition → LVM → filesystem → mount
task. Requires Vagrant plus a provider (VirtualBox anywhere, or libvirt/KVM
on Linux — the script detects which you have and offers to install the
`vagrant-libvirt` plugin if that's the better fit).

Manage it from `vagrant/`: `vagrant halt` to stop, `vagrant reload` to
reboot, `vagrant destroy -f` to remove entirely.

Two upstream bugs are worked around here, both of which cost real time to
diagnose:

* **The box comes from Rocky's mirror, not Vagrant Cloud.** The
  `rockylinux/10` entry on Vagrant Cloud currently points at a deleted
  image and fails to download, so `vagrant/Vagrantfile` pins `box_url`
  straight at `download.rockylinux.org`.
* **The libvirt box declares the wrong disk size.** Its `metadata.json`
  says `"virtual_size": 5` (GB) while the qcow2 inside is 10 GiB, so
  vagrant-libvirt creates a 5G volume that truncates the root partition.
  Every VM then drops into dracut emergency mode — no userspace, no DHCP,
  no SSH — and Vagrant surfaces that only as *"Waiting for domain to get
  an IP address..."* forever, which looks like a network fault and sends
  you hunting in the wrong place entirely. The Vagrantfile forces
  `machine_virtual_size` (20G, override with `RHCE_LAB_ROOT_GB`).

**If the VMs hang at "Waiting for domain to get an IP address..."** the
cause is almost always one of two things. Check the console first —
`sudo virsh screenshot <domain> /tmp/vm.ppm` — because if it shows an
emergency shell the problem isn't networking at all. If the guest booted
fine, suspect a host firewall dropping DHCP on the bridge: `ufw` with a
default-deny policy and no `virbr1` rule does exactly this. The setup
script now detects that case and offers to add the rules.
* **If a node reports SELinux `Disabled`,** it has been flagged for a
  filesystem relabel — run `vagrant reload` and it comes back `Enforcing`.
  The setup script prints each node's mode at the end so you know.
* Trouble attaching the spare disk? `RHCE_LAB_EXTRA_DISK=0
  ./scripts/vm-lab-setup.sh` skips it; the storage task then reports its
  state checks as skipped and everything else still works.

### Option 3 — your own RHEL/Rocky/Alma machines

Point the simulator at anything reachable over SSH:

```bash
export RHCE_SIM_NODES="rhel-1,rhel-2"   # names as they appear in YOUR inventory
export RHCE_SIM_WORKDIR="$HOME/ansible"
```

You supply the `inventory` and `ansible.cfg` (the first tasks in Domain 3
walk you through writing them). For full grading the nodes want `getenforce`
returning `Enforcing`, and a spare unpartitioned disk on at least one node
for the storage task. Use machines you can trash — tasks partition disks
and rewrite service configs.

### Single machine, no lab at all

The default works: put `localhost ansible_connection=local` in your
inventory and playbooks configure the control node itself. Use a VM you can
throw away, because they really will change it.

### Environment variables

| Env var | Default | Meaning |
|---|---|---|
| `RHCE_SIM_WORKDIR` | `~/ansible` | Your Ansible working directory (ansible.cfg, inventory, playbooks) |
| `RHCE_SIM_NODES` | `localhost` | Comma-separated managed nodes used in task wording and state checks |
| `RHCE_SIM_REMOTE_USER` | `devops` | Remote user referenced by tasks |
| `RHCE_SIM_SPARE_DISK` | `/dev/vdb` | Spare block device the storage task partitions. virtio/KVM uses `vdb`, VirtualBox/SATA uses `sdb`; `vm-lab-setup.sh` detects it and prints the right export. |
| `RHCE_LAB_PROVIDER` | auto | VM lab only: force `virtualbox` or `libvirt` |
| `RHCE_LAB_EXTRA_DISK` | `1` | VM lab only: set `0` to skip the spare disk |
| `RHCE_LAB_MEMORY` / `RHCE_LAB_CPUS` | `1024` / `1` | VM lab only: per-VM resources |

## Platform support

The control node — the machine running `rhce_simulator.py` and Ansible —
must be Linux or macOS. **Ansible has no native Windows control node**, so
on Windows you run everything inside WSL2. Managed nodes are always RHEL
family (Rocky 10 in both labs); the exam is a RHEL exam and the task
catalog assumes it throughout.

| Host | Simulator | Docker lab | VM lab |
|---|---|---|---|
| **Linux** | ✅ native | ✅ | ✅ VirtualBox or libvirt/KVM |
| **macOS (Intel)** | ✅ native | ✅ Docker Desktop | ✅ VirtualBox |
| **macOS (Apple Silicon)** | ✅ native | ✅ Docker Desktop | ⚠️ see below |
| **Windows** | ✅ via WSL2 | ✅ Docker Desktop + WSL2 backend | ⚠️ see below |

**Windows.** Run `rhce_simulator.py` and `lab-setup.sh` from inside WSL2,
not PowerShell. Docker Desktop's WSL2 backend makes `docker` work from a
WSL prompt with no extra setup, so the Docker lab is the path of least
resistance. The VM lab is awkward here: Vagrant installed *inside* WSL2
can't drive VirtualBox or Hyper-V on the Windows host without extra
configuration. If you want VMs on Windows, install and run Vagrant on
Windows itself, then point WSL2's simulator at the resulting VMs using
Option 3.

**Apple Silicon.** The Docker lab works — Rocky publishes arm64 images.
The VM lab is the weak spot: VirtualBox support on arm64 is poor and Rocky
ships no VMware Vagrant box, so there's no clean scripted path. For SELinux
grading on an M-series Mac, use Option 3 with a Rocky/Alma VM under UTM,
Parallels or VMware Fusion, or a cloud VM.

## Task catalog

42 tasks across 20 categories, mapped to the official page's own 11
objective domains (not an earlier internal 7-domain grouping) — including
two domains most RHCE prep material still misses: **Domain 6 (Git source
control)** and **Domain 7 (VS Code / execution-environment workflow)**,
added to the objectives alongside ansible-navigator and easy to miss if
your reference material predates that update. Also covers ansible.cfg /
ansible-navigator.yml, SSH key distribution & privilege escalation,
inventories, ad-hoc commands, playbook authoring, variables & facts, loops
& conditionals, handlers & block/rescue, Jinja2 templates, file content &
archiving, roles, RHEL System Roles (~40+ role catalog now, not just the
classic handful), collections, Vault (including the vault-ID pattern), and
automated storage / users / scheduling administration.

**SELinux** (Domain 10's `security (SELinux modes, booleans, file
contexts)` bullet) gets its own category: modes, booleans, port labelling
and file contexts — including the trap that `sefcontext` writes the rule
while `restorecon` is what actually applies it, and that these modules are
split across `ansible.posix` and `community.general`. Error handling
covers `failed_when` / `changed_when` / `ignore_errors` / `assert`
alongside handlers and block/rescue, because command and shell tasks can
be neither idempotent nor failure-aware without them.

Domain 1 (RHCSA foundation) has no dedicated category here by design —
that's the sibling rhcsa-simulator's job.

`python3 rhce_simulator.py --list-tasks` shows the live list.

## Running the test suite

```bash
python3 -m pytest -q
```

Unit tests mock the Ansible runner — they never require ansible-core,
managed nodes, or root. `pytest` is the only development dependency; the
simulator itself needs nothing beyond the standard library.

On distributions that mark the system Python as externally managed (Arch,
recent Debian/Fedora), `pip install pytest` is refused system-wide — use a
throwaway virtualenv:

```bash
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m pytest -q
```

## Roadmap

* Exam clock + timed mode parity with rhcsa-simulator
* More tasks per category (target ≥3 each)
* SM-2 spaced-repetition practice mode (port from rhcsa-simulator)
* Optional AI feedback on submitted playbooks via `ANTHROPIC_API_KEY`

## License

MIT
