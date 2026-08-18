# RHCE Exam Simulator

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/troggman)

**NOTE: I have not done the EX294 exam! I do not yet know if this will help you pass. ANY and ALL feedback, especially from those that have already written and/or passed the exam will be extremely helpful!**

RHCE **EX294 (RHEL 10)** exam simulator — a command-line trainer for Red
Hat's Ansible automation exam (renamed the *Red Hat Certified Advanced
System Administrator in Ansible Exam* in May 2026, same content; kept
"RHCE" in the project name since that's what people search for). Grades
the way the real exam does — **by results, not methods**: it runs your
playbooks against your own inventory and inspects the state they produce.

Sibling project to [rhcsa-simulator](https://github.com/TroggoMan/rhcsa-simulator)
(RHCSA EX200 v10), sharing its conventions: Python standard library only,
task auto-discovery, SQLite progress tracking.

Task content was audited against Red Hat's official EX294 page and current
Ansible docs on 2026-07-27 — see `config/exam_objectives.py` and
`config/learn_content.py` for sourcing notes.

## How grading works

Every task is validated in up to three layers:

1. **Artifacts** — the required files exist and contain what was asked
   (static checks; always run).
2. **Execution** — the playbook passes `--syntax-check`, runs cleanly
   against *your* inventory and `ansible.cfg`, and is **idempotent** (a
   second run must report `changed=0` — the exam's favorite trap).
3. **State** — ad-hoc queries against your managed nodes confirm the end
   state the playbook was supposed to produce.

## Install

```bash
git clone https://github.com/TroggoMan/rhce-simulator.git
cd rhce-simulator
./scripts/bootstrap.sh
```

`bootstrap.sh` detects your OS/package manager, installs what's needed,
and builds a lab. It asks before installing anything.

```bash
./scripts/bootstrap.sh --lab vm       # QEMU/KVM VMs — grades everything, incl. SELinux
./scripts/bootstrap.sh --lab docker   # containers — faster/lighter, no SELinux
./scripts/bootstrap.sh --lab none     # just the tooling; I'll bring my own nodes
./scripts/bootstrap.sh --dry-run      # show exactly what it would do, change nothing
./scripts/bootstrap.sh --yes          # unattended
```

| Package manager | Platforms |
|---|---|
| `pacman` | Arch, CachyOS, Manjaro, EndeavourOS |
| `apt` | Debian, Ubuntu, Mint, Pop!_OS |
| `dnf` | Fedora, RHEL, Rocky, Alma, CentOS Stream |
| `zypper` | openSUSE, SLES |
| `brew` | macOS |

Windows: run it inside WSL2 — Ansible has no native Windows control node.
See **Platform support**.

**This doesn't write your `inventory` or `ansible.cfg`.** Nodes come up
with exam-style bootstrap access only — root, reachable by password.
Building your own inventory/ansible.cfg/automation user from that is your
actual first task; see **Lab setup** and `rhce_simulator.py --learn`
(Configuring managed nodes).

Don't want the script installing things? Everything it does is documented
in **Lab setup** below, and `scripts/lab-setup.sh` / `vm-lab-setup.sh` work
standalone once you have the tooling. The one step that's easy to miss —
`ansible-core` ships no collections:

```bash
ansible-galaxy collection install ansible.posix community.general
```

**Want isolation from your host instead?** Any Linux container works the
same way — spin one up yourself (`docker run -dit --name control
rockylinux/rockylinux:10 bash`, then exec in) and run the exact steps
above from inside it. Nothing container-specific to know; `bootstrap.sh`
detects RHEL-family either way. It just can't build the Docker/VM lab
*from inside itself* without Docker/KVM access of its own — use `--lab
none` there and build the lab on your host instead, and `docker network
connect rhce-lab_default control` to resolve its nodes by hostname.

## Vim for YAML

The exam gives you no internet and no plugins — get a `~/.vimrc` short
enough to retype from memory:

```vim
syntax on
set number
set expandtab
set shiftwidth=2
set softtabstop=2
set tabstop=2
set colorcolumn=80
```

YAML needs 2-space indents and breaks on tabs; `expandtab` makes every
<kbd>Tab</kbd> press insert spaces instead. Two more worth memorizing for
ad-hoc use, not the vimrc itself:

- `:set list` — shows tabs/trailing whitespace, both of which break YAML
  silently. Run it the moment something won't parse.
- `:retab` — converts existing tabs to spaces once `expandtab` is on, for
  when you paste something that already has them.

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

`--focus` ranks every category worst-first from your session history
(never-attempted ranks weakest of all) and builds a session from the four
worst. Run `--quick`/`--exam`/`--practice` a few times first so it has
something to rank.

Inside a session: type a task number to read it, do the work **in another
terminal**, then `v <n>` to validate (`h <n>` for hints, `q` to finish).

`--learn` is interactive: pick a domain, pick a category, get a concept
explanation, real module syntax, common mistakes, and exam tips. `[P]`
from a topic screen jumps straight into practicing it.

## Lab setup

**This is the part that matters.** The simulator grades by running your
playbooks against real managed nodes, so it needs nodes. `bootstrap.sh`
does this for you — this section is the detail behind it, for when you
want to choose deliberately or drive the scripts yourself.

| | Docker lab | VM lab | Your own machines |
|---|---|---|---|
| Command | `./scripts/lab-setup.sh` | `./scripts/vm-lab-setup.sh` | manual |
| Nodes | 4 containers | 4 VMs | however many you have |
| Setup time | ~2 min | ~10 min (downloads a ~1GB box) | — |
| Disk/RAM cost | low | ~3GB RAM, ~15GB disk | — |
| **Grades SELinux** | ❌ impossible | ✅ yes | ✅ if enforcing |
| **Grades raw-disk task** | ❌ no spare disk | ✅ yes | ✅ if you attach one |
| **Grades network role** | ❌ no NetworkManager | ✅ yes | ✅ yes |
| Everything else | ✅ | ✅ | ✅ |

**Neither script writes an `inventory` or `ansible.cfg`.** Both hand you
nodes with root/password bootstrap access and print the hostname/port/
password when done. Turning that into a working inventory is your first
task — see `rhce_simulator.py --learn` (Configuring managed nodes) for the
bootstrap sequence (`-k`/`-K`, then switch to your own key). Build `dev`
and `prod` groups in that same pass, each with at least one host — several
tasks elsewhere in the catalog assume both already exist and fail on a
missing group, not a wrong playbook, if you skip this.

**Which one?** The VM lab is the faithful one — real kernel, real
enforcement, a real spare disk — practise here if you're sitting the exam
soon. The Docker lab is the fast one and grades far more than you'd
expect: real SELinux policy store, just no kernel enforcement. Use Docker
to drill, use the VMs to be sure.

### Option 1 — VM lab (full fidelity)

```bash
./scripts/vm-lab-setup.sh
# prints each node's SSH port + root password — build your inventory
# and ansible.cfg from that (see --learn managed_nodes), THEN:
python3 rhce_simulator.py --exam
```

`RHCE_SIM_NODES` doesn't need setting by hand — the simulator detects
`kirk`/`spock`/`mccoy`/`scotty` via `vagrant status` automatically. Four
Rocky Linux 10 VMs via Vagrant, **SELinux enforcing**, with a blank 10G
disk on `scotty` for the partition → LVM → filesystem → mount task.
Requires Vagrant plus a provider (VirtualBox anywhere, or libvirt/KVM on
Linux — the script offers to install the `vagrant-libvirt` plugin).

Everything in the catalog grades end to end here.

```bash
./scripts/vm-lab-teardown.sh            # power the VMs off, keep them
./scripts/vm-lab-teardown.sh --destroy  # delete them and their disks
./scripts/vm-lab-teardown.sh --status   # show what's running
```

### Option 2 — Docker lab (fast, light, runs anywhere)

```bash
./scripts/lab-setup.sh
# prints each node's SSH port + root password — build your inventory
# and ansible.cfg from that (see --learn managed_nodes), THEN:
python3 rhce_simulator.py --quick
```

Builds 4 systemd-enabled Rocky Linux 10 containers (`kirk`, `spock`,
`mccoy`, `scotty`) on `127.0.0.1:2201`-`2204`. Tear down with `docker
compose -f docker/docker-compose.yml down -v`. `RHCE_SIM_NODES` is
auto-detected here too, via `docker ps`.

**SELinux mostly works here, and it isn't faked.** Real
`selinux-policy-targeted` store, real `semanage`, all ~314 genuine
booleans, real port types and file contexts — invent a boolean name and
policy rejects it same as anywhere. What's simulated: the presence of a
running kernel, since containers share the host's and get no `selinuxfs`
of their own (`docker/selinux-sim/` patches just that; see its header for
exactly what it does and doesn't buy you). Consequently, still not
gradeable here:

- **Relabelling.** `semanage fcontext` rules grade fine; `restorecon` has
  no kernel to write labels through, so those two checks are **skipped**,
  never failed.
- **Denials** — no enforcement means no AVCs for `ausearch`/`audit2allow`.
- **The raw-disk storage task** — privileged containers share the host's
  `/dev`, so a loop device would be visible to every node at once.
- **The `network` system-role task**, which needs NetworkManager.

Skipped checks don't count against your score. Firewalld works, but is
less faithful than a real netfilter stack.

### Resetting node state between attempts

Practice leaves state behind — users, LVM volumes, cron jobs, vault files,
SELinux labels — none of which a real retake would carry over.
`scripts/lab-reset.sh` puts nodes back to a clean slate fast:

```bash
./scripts/lab-reset.sh                        # auto-detects Docker or VM lab
./scripts/lab-reset.sh --docker               # force-recreates the containers (~seconds)
./scripts/lab-reset.sh --vm --save-snapshot   # once, right after vm-lab-setup.sh finishes
./scripts/lab-reset.sh --vm                   # restores that snapshot (~seconds)
```

Docker resets by recreating containers from the already-built image
(bootstrap access is baked in). VM resets by Vagrant snapshot restore —
take the baseline snapshot once, then every reset after is fast.

**A reset wipes your OWN bootstrap setup too** — automation user, SSH key,
sudoers only exist because you put them there. By design, not a bug. Save
your bootstrap playbook as a file and `-u root -k` gets you back in
seconds; one-off ad-hoc commands mean retyping them.

That resets the *nodes*. To also clear your own working directory
(playbooks/inventory/`ansible.cfg`) and start a session exam-blank without
rebuilding a lab: `./scripts/reset-workdir.sh` — archives it first
(`$WORKDIR-archive-<timestamp>.tar.gz`), never deletes outright. Your
tracked progress history is untouched either way; that's
`--reset-progress`.

Use the script rather than bare `vagrant` commands — Vagrant is
directory-scoped (acts on the first Vagrantfile it finds walking up from
`$PWD`), so a stray one elsewhere silently no-ops instead of touching your
lab. The teardown script pins `VAGRANT_CWD` and verifies against the
hypervisor directly rather than trusting Vagrant's exit code.

Two upstream Vagrant bugs are worked around here:

* **The box comes from Rocky's mirror, not Vagrant Cloud** — the
  `rockylinux/10` Vagrant Cloud entry points at a deleted image, so
  `vagrant/Vagrantfile` pins `box_url` at `download.rockylinux.org`.
* **The libvirt box under-declares its disk size** (5G metadata, 10G
  actual qcow2), which truncates the root partition and drops VMs into
  dracut emergency mode — Vagrant just shows "Waiting for domain to get an
  IP address..." forever. Forced to 20G via `machine_virtual_size`
  (override with `RHCE_LAB_ROOT_GB`).

**VMs hanging at "Waiting for domain to get an IP address..."?** Check the
console first (`sudo virsh screenshot <domain> /tmp/vm.ppm`) — an
emergency shell means it's not networking. Otherwise, suspect a host
firewall dropping DHCP on the bridge (`ufw` with no `virbr1` rule does
this; the setup script detects and offers to fix it).

* **SELinux `Disabled`?** Flagged for a relabel — `vagrant reload` fixes it.
* **Spare disk trouble?** `RHCE_LAB_EXTRA_DISK=0 ./scripts/vm-lab-setup.sh`
  skips it; the storage task then reports those checks as skipped.

### Option 3 — your own RHEL/Rocky/Alma machines

```bash
export RHCE_SIM_NODES="rhel-1,rhel-2"   # names as they appear in YOUR inventory
export RHCE_SIM_WORKDIR="$HOME/ansible"
```

You supply the `inventory` and `ansible.cfg`. For full grading, nodes want
`getenforce` returning `Enforcing` and a spare unpartitioned disk on at
least one for the storage task. Use machines you can trash.

### Single machine, no lab at all

The default works: `localhost ansible_connection=local` in your inventory,
playbooks configure the control node itself. Use a throwaway VM — tasks
really do partition disks and rewrite service configs.

### Environment variables

| Env var | Default | Meaning |
|---|---|---|
| `RHCE_SIM_WORKDIR` | `~/ansible` | Your Ansible working directory (ansible.cfg, inventory, playbooks) |
| `RHCE_SIM_NODES` | auto-detected, else `localhost` | Comma-separated managed nodes for task wording and state checks. Unset, checks `docker ps` then `vagrant status`. |
| `RHCE_SIM_REMOTE_USER` | `devops` | Automation user YOU create during bootstrap, referenced by task wording |
| `RHCE_SIM_SPARE_DISK` | `/dev/vdb` | Storage-task device. virtio/KVM uses `vdb`, VirtualBox/SATA uses `sdb`; `vm-lab-setup.sh` detects and prints it. |
| `RHCE_LAB_ROOT_PASSWORD` | `rhce-lab` | Root password both labs set for bootstrap access |
| `RHCE_LAB_PROVIDER` | auto | VM lab: force `virtualbox` or `libvirt` |
| `RHCE_LAB_EXTRA_DISK` | `1` | VM lab: `0` to skip the spare disk |
| `RHCE_LAB_MEMORY` / `RHCE_LAB_CPUS` | `1024` / `1` | VM lab: per-VM resources |

## Platform support

The control node (running `rhce_simulator.py` and Ansible) must be Linux
or macOS — no native Windows support, run it inside WSL2. Managed nodes
are always RHEL family (Rocky 10 in both labs).

| Host | Simulator | Docker lab | VM lab |
|---|---|---|---|
| **Linux** | ✅ native | ✅ | ✅ VirtualBox or libvirt/KVM |
| **macOS (Intel)** | ✅ native | ✅ Docker Desktop | ✅ VirtualBox |
| **macOS (Apple Silicon)** | ✅ native | ✅ Docker Desktop | ⚠️ see below |
| **Windows** | ✅ via WSL2 | ✅ Docker Desktop + WSL2 backend | ⚠️ see below |

**Windows.** Run everything from inside WSL2, not PowerShell. Docker
Desktop's WSL2 backend makes `docker` work from a WSL prompt with no extra
setup — the Docker lab is the path of least resistance. Vagrant inside
WSL2 can't drive VirtualBox/Hyper-V on the Windows host; if you want VMs,
run Vagrant on Windows itself and point WSL2's simulator at the resulting
VMs (Option 3).

**Apple Silicon.** Docker lab works (Rocky publishes arm64 images). VM lab
is the weak spot — poor VirtualBox arm64 support, no Rocky VMware box. The
Docker lab's SELinux support (booleans, port labelling, permissive
domains, enforcing mode) covers most of the catalog with no VM at all;
only relabelling still needs a real kernel (Option 3 with UTM/Parallels/
VMware Fusion, or a cloud VM).

## Task catalog

82 tasks across 20 categories, mapped to the official page's 11 objective
domains — including two most prep material still misses: **Domain 6 (Git
source control)** and **Domain 7 (VS Code / execution-environment
workflow)**. Also covers ansible.cfg/ansible-navigator.yml, SSH key
distribution & privilege escalation, inventories, ad-hoc commands,
playbook authoring, variables & facts, loops & conditionals, handlers &
block/rescue, Jinja2 templates, file content & archiving, roles, RHEL
System Roles, collections, Vault (incl. vault-ID), and storage/users/
scheduling administration.

**SELinux** gets its own category: modes, booleans, port labelling, file
contexts — including that `sefcontext` writes the rule while `restorecon`
applies it, split across `ansible.posix`/`community.general`. Error
handling covers `failed_when`/`changed_when`/`ignore_errors`/`assert`
alongside handlers and block/rescue.

Domain 1 (RHCSA foundation) has no category here by design — that's
rhcsa-simulator's job.

`python3 rhce_simulator.py --list-tasks` shows the live list.

## Running the test suite

```bash
python3 -m pytest -q
```

Unit tests mock the Ansible runner — never require ansible-core, managed
nodes, or root. `pytest` is the only dev dependency.

On distributions with an externally-managed system Python (Arch, recent
Debian/Fedora):

```bash
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m pytest -q
```

## Uninstall

```bash
./scripts/uninstall.sh          # asks before removing each piece it finds
./scripts/uninstall.sh --yes    # don't ask
```

Tears down the Docker lab and the VM lab, whichever exist. Your practice
workdir is kept unless you confirm otherwise (not archived, a real
delete). It doesn't remove this repo clone or your tracked progress history
— `rm -rf` the clone yourself when you're done, or `--reset-progress` for
just the history.

## Roadmap

* Exam clock + timed mode parity with rhcsa-simulator
* More tasks per category (target ≥3 each)
* SM-2 spaced-repetition practice mode (port from rhcsa-simulator)
* Optional AI feedback on submitted playbooks via `ANTHROPIC_API_KEY`

## License

MIT
