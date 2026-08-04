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
everything needed, configures services and group membership, and builds a
lab. It asks before installing anything and never installs silently.

**It deliberately does NOT write your `inventory` or `ansible.cfg`.** Every
node comes up with exam-style bootstrap access only — root, reachable by
password — exactly what the real exam hands you. Building your own
inventory, `ansible.cfg`, automation user, SSH key and sudoers from that
is your actual first task, not something a script should do for you; see
**Lab setup** below and `rhce_simulator.py --learn` (Configuring managed
nodes) for the exact bootstrap sequence.

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
python3 rhce_simulator.py --focus             # weighted practice on YOUR weakest categories
python3 rhce_simulator.py --list-tasks        # catalog overview
python3 rhce_simulator.py --learn             # browse domains -> topics -> real study content
python3 rhce_simulator.py --history           # past sessions & per-category pass rate
python3 rhce_simulator.py --reset-progress    # wipe tracked history (asks to confirm)
```

`--focus` reads your session history, ranks every category worst-first
(never-attempted categories rank as the weakest of all — an untested spot
is worse than a shaky pass rate), and builds a practice session out of the
four worst. Run `--quick`/`--exam`/`--practice` a few times first so it has
something to rank; with no history yet it just spreads across everything.

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

**Neither script writes an `inventory` or `ansible.cfg` for you.** Both
hand you nodes with exam-style bootstrap access only — root, reachable by
password — and print exactly that (hostname, SSH port, password) when
they finish. Turning it into a working inventory/ansible.cfg/automation
user is your first task; see `rhce_simulator.py --learn` (Configuring
managed nodes) for the bootstrap sequence (`-k`/`-K`, then switch to your
own key). Neither script installs software without asking first.

**Which one?** The VM lab is the faithful one — real kernel, real
enforcement, a real spare disk — and it is what to practise on if you are
sitting the exam. The Docker lab is the fast one, and it now grades far
more than it used to: the nodes carry the genuine SELinux policy store, so
booleans, port types and file-context rules are real and graded for real.
What it cannot reproduce is kernel *enforcement*, which costs it three
checks (see below).

Use Docker to drill, use the VMs to be sure.

### Option 1 — VM lab (full fidelity — practise here)

```bash
./scripts/vm-lab-setup.sh
# prints each node's SSH port + root password — build your own inventory
# and ansible.cfg from that (see --learn managed_nodes), THEN:
export RHCE_SIM_NODES="morty,summer,jerry"
python3 rhce_simulator.py --exam
```

Three Rocky Linux 10 VMs via Vagrant, **SELinux enforcing**, with a blank
10G disk attached to `jerry` for the partition → LVM → filesystem → mount
task. Requires Vagrant plus a provider (VirtualBox anywhere, or libvirt/KVM
on Linux — the script detects which you have and offers to install the
`vagrant-libvirt` plugin if that's the better fit).

Everything in the catalog grades end to end here. Nothing is skipped and
nothing is simulated.

Stop it — from anywhere in the repo:

```bash
./scripts/vm-lab-teardown.sh            # power the VMs off, keep them
./scripts/vm-lab-teardown.sh --destroy  # delete them and their disks
./scripts/vm-lab-teardown.sh --status   # show what's running
```

### Option 2 — Docker lab (fast, light, runs anywhere)

```bash
./scripts/lab-setup.sh
# prints each node's SSH port + root password — build your own inventory
# and ansible.cfg from that (see --learn managed_nodes), THEN:
export RHCE_SIM_NODES="morty,summer,jerry,beth,rick"
python3 rhce_simulator.py --quick
```

Builds 5 systemd-enabled Rocky Linux 10 containers (`morty`, `summer`,
`jerry`, `beth`, `rick`) on `127.0.0.1:2201`-`2205`. Tear down with
`docker compose -f docker/docker-compose.yml down -v`.

**SELinux mostly works here, and it is not faked.** The nodes install the
real `selinux-policy-targeted` store, and `semanage`/libsemanage
manipulate it for real — all ~314 genuine booleans, real port types, real
file contexts. Invent a boolean name and policy rejects it exactly as it
would anywhere else. Booleans, port labelling and permissive domains all
grade end to end, node state included.

One thing is simulated, and only one: the presence of a running kernel.
SELinux enforcement is a host-kernel feature, containers share the host's
kernel and get no `selinuxfs` of their own, so every SELinux tool starts by
asking the kernel "are you there?", gets no, and refuses to touch even the
parts that are pure disk I/O. `docker/selinux-sim/` patches exactly those
kernel calls and leaves everything else alone — see the header of
`rhce_selinux_sim.py`, which documents precisely what that does and does
not buy you.

**What still cannot be graded here:**

- **Relabelling effects.** `semanage fcontext` rules are stored and graded;
  `restorecon` has no kernel to write labels through, so `ls -Z` reports
  nothing. Those two checks are marked **skipped**, never failed.
- **Denials.** No enforcement means no AVCs — nothing for `ausearch` or
  `audit2allow` to work on.
- **The raw-disk storage task.** Privileged containers share the host's
  `/dev` and `/sys`, so a loop device is visible to *every* node at once.
  That would defeat the very thing the task grades — acting only on hosts
  that have the disk — so it is deliberately not offered.
- **The `network` system-role task**, which needs NetworkManager.

Skipped checks are excluded from the score denominator, so a correct
answer is never penalised for a lab that cannot observe it. Firewalld
works, but is less faithful than a real host's netfilter stack.

### Resetting node state between attempts

Practice sessions leave state behind on the managed nodes — users, LVM
volumes, cron jobs, vault files, SELinux labels — none of which a real
exam retake would carry over. `scripts/lab-reset.sh` puts the nodes back
to a clean slate fast, without the multi-minute rebuild teardown+setup
would cost:

```bash
./scripts/lab-reset.sh                        # auto-detects Docker or VM lab
./scripts/lab-reset.sh --docker               # force-recreates the containers (~seconds)
./scripts/lab-reset.sh --vm --save-snapshot   # once, right after vm-lab-setup.sh finishes
./scripts/lab-reset.sh --vm                   # restores that snapshot (~seconds)
```

The Docker lab resets by recreating every container from its already-built
image (no rebuild needed) — bootstrap access (root/password) is baked into
the image, so a fresh container already has it. The VM lab resets via a
Vagrant snapshot restore — take the baseline snapshot once, before you
start practicing, then every reset after that is fast.

**A reset wipes your OWN bootstrap setup too** — your automation user, SSH
key and sudoers only exist because you put them there, so they're gone
along with everything else. That's by design (the node really is back to
"root/password, nothing else"), not a bug. If you saved your bootstrap
playbook as a real file, re-running it with `-u root -k` gets you back to
a working setup in seconds; if you did it all as one-off ad-hoc commands,
you'll be retyping them. Save the playbook.

Use the script rather than bare `vagrant` commands. Vagrant is
directory-scoped — it acts on the first Vagrantfile it finds walking up from
`$PWD` — so `vagrant halt` from the repo root does nothing to a lab defined
in `vagrant/`, and if a stray Vagrantfile is sitting up there it finds that
one instead, sees a machine that was never created, and **exits 0 having
touched nothing** while the VMs keep running. The teardown script pins
`VAGRANT_CWD` at `vagrant/`, then asks the hypervisor directly whether the
VMs actually stopped rather than trusting Vagrant's exit code.

Driving Vagrant by hand still works, as long as you do it from `vagrant/`:
`vagrant reload` to reboot (needed after an SELinux relabel), `vagrant ssh
<node>` for a shell on one.

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

### The control node (both labs)

`lab-setup.sh` also brings up a `control` container — the machine you work
*from*, as opposed to the managed nodes you work *on*:

```bash
docker exec -it control bash
```

Rocky Linux 10 with `ansible-core` and `rhel-system-roles` preinstalled.
That matters more than it sounds:

- **`redhat.rhel_system_roles.<role>` resolves for real.** That collection
  lives on Red Hat Automation Hub, not public Galaxy, so
  `ansible-galaxy collection install redhat.rhel_system_roles` fails for
  anyone without a subscription. The Rocky RPM provides the genuine
  namespace.
- **ansible-core is the version RHEL ships (2.16)**, not whatever your
  workstation is on. Module behaviour and deprecations differ.
- **Managed nodes are plain hostnames on port 22** (`morty`, `summer`,
  `jerry`, `beth`, `rick`) rather than `127.0.0.1:220x`, so the inventory
  you write looks like the one the exam wants.

Your working directory and this repo are both mounted inside it, so you
can edit playbooks with your own tools on the host and run the simulator
either place. Use it with the VM lab too — point `RHCE_SIM_NODES` at the
VM addresses; they route via `host.docker.internal`.

Working from your own workstation still works fine, and everything grades
the same. You just won't have the `redhat.` namespace or the exam's
ansible-core version.

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
| `RHCE_SIM_REMOTE_USER` | `devops` | Remote user referenced by task wording — the automation user YOU create during bootstrap, not something the lab creates for you |
| `RHCE_SIM_SPARE_DISK` | `/dev/vdb` | Spare block device the storage task partitions. virtio/KVM uses `vdb`, VirtualBox/SATA uses `sdb`; `vm-lab-setup.sh` detects it and prints the right export. |
| `RHCE_LAB_ROOT_PASSWORD` | `rhce-lab` | Root password both labs set for bootstrap-only access — override before building a lab if you want a different one |
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

82 tasks across 20 categories, mapped to the official page's own 11
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
