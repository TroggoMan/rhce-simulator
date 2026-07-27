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

## Requirements

| What | Needed for | Notes |
|---|---|---|
| **Python 3.9+** | the simulator itself | Standard library only — there is nothing to `pip install` and no virtualenv required to run it. |
| **ansible-core** | execution + node-state grading | Without it the simulator still runs and grades your files statically; it just can't run your playbooks. |
| **ansible-navigator** | the navigator tasks | Recommended — the exam environment uses it. `pip install ansible-navigator`. |
| **git** | the source-control tasks | The lab "remote" is a local bare repo, so no network or GitHub account is needed. |
| **Docker + compose plugin** | the containerised lab | Only if you use `scripts/lab-setup.sh` rather than your own VMs. |

## Installation

```bash
git clone https://github.com/TroggoMan/rhce-simulator.git
cd rhce-simulator

# Nothing to build or install — verify it runs:
python3 rhce_simulator.py --list-tasks
```

Then set up managed nodes one of two ways — the containerised lab or your
own VMs (see **Lab setup** below), and point the simulator at them:

```bash
./scripts/lab-setup.sh                                   # builds the 5-node Docker lab
export RHCE_SIM_NODES="morty,summer,jerry,beth,rick"
export RHCE_SIM_WORKDIR="$HOME/ansible"
```

Installing ansible-core and ansible-navigator, if you don't have them:

```bash
python3 -m pip install --user ansible-core ansible-navigator
# or, on RHEL/Rocky/Alma:  sudo dnf install ansible-core
```

`scripts/lab-setup.sh` will offer to install Docker and ansible-core for
you if they're missing — it always asks first and never installs silently.

## Quick start

```bash
git clone https://github.com/TroggoMan/rhce-simulator.git
cd rhce-simulator

python3 rhce_simulator.py --quick             # 5 random tasks
python3 rhce_simulator.py --exam              # full 4-hour-style exam (20 tasks)
python3 rhce_simulator.py --practice vault    # drill one category
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

| Env var | Default | Meaning |
|---|---|---|
| `RHCE_SIM_WORKDIR` | `~/ansible` | Your Ansible working directory (ansible.cfg, inventory, playbooks) |
| `RHCE_SIM_NODES` | `localhost` | Comma-separated managed nodes used in task wording and state checks |
| `RHCE_SIM_REMOTE_USER` | `devops` | Remote user referenced by tasks |

* **Single machine:** the default works — put `localhost ansible_connection=local`
  in your inventory. Playbooks then configure the control node itself, so use a
  VM you can trash.
* **Docker lab (recommended for most people):** `./scripts/lab-setup.sh`
  installs Docker/ansible-core if missing (asks first), then builds a
  disposable 5-node lab — `morty`, `summer`, `jerry`, `beth`, `rick`, all
  systemd-enabled Rocky Linux 10 — reachable at `127.0.0.1:2201`-`2205`, and
  writes an inventory + `ansible.cfg` into `$RHCE_SIM_WORKDIR`. Works the
  same way on Linux, macOS, and Windows (via WSL2 — see below). Then:
  ```bash
  export RHCE_SIM_NODES="morty,summer,jerry,beth,rick"
  python3 rhce_simulator.py --quick
  ```
  **Known limitation:** SELinux enforcement is a host-kernel feature, not a
  container one — containers share the host's kernel and get no selinuxfs of
  their own, so no container can enforce SELinux regardless of how it's
  configured (this is *also* true of rhcsa-simulator's containerized dev
  environment; see its CLAUDE.md). The simulator handles this honestly
  rather than silently: SELinux tasks always grade your playbook's
  *content*, then probe the managed nodes for a live SELinux subsystem and
  mark the execution/state checks **skipped** — never failed — when there
  isn't one. Skipped checks are excluded from both the pass decision and
  the score, so a correct answer is never penalised for a lab that can't
  observe it. The same treatment applies to the `network` system-role task
  (needs NetworkManager) and the raw-disk storage task (needs a spare
  blank disk). To grade any of those end to end, use a real VM (below).
  Firewalld mostly works but is less faithful than a real host's netfilter
  stack.
  **Windows:** run `lab-setup.sh` and `rhce_simulator.py` from inside WSL2,
  not native PowerShell — Ansible's control node doesn't run natively on
  Windows. Docker Desktop's WSL2 backend makes `docker` work from a WSL
  prompt without extra setup.
* **Real lab (full fidelity):** point `RHCE_SIM_NODES` at one or more real
  RHEL 10 / Rocky 10 / Alma 10 VMs reachable over SSH instead of the Docker
  lab — needed if you want SELinux enforcement and firewalld to behave
  exactly like the exam. The first tasks in domain 1 walk you through key
  distribution and privilege escalation either way.

  ```bash
  export RHCE_SIM_NODES="rhel-1,rhel-2"     # names as they appear in YOUR inventory
  export RHCE_SIM_WORKDIR="$HOME/ansible"
  python3 rhce_simulator.py --practice selinux
  ```

  Confirm the VM can actually grade SELinux before relying on it —
  `getenforce` should say `Enforcing` (or at minimum `Permissive`), and
  `/sys/fs/selinux` must exist, which is what the simulator probes for.
  For the raw-disk storage task, attach a spare unpartitioned virtual disk
  (a second 10G disk is plenty) to one VM and leave the others without one
  — the task is specifically about detecting which hosts have it.

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
