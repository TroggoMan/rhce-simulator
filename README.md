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

Sibling project to [rhcsa-simulator](https://github.com/justbest23/rhcsa-simulator)
(RHCSA EX200 v10), sharing its conventions: Python standard library only,
task auto-discovery, SQLite progress tracking.

Objectives and task content were audited against Red Hat's current
official EX294 page and current Ansible tooling docs on 2026-07-23 — see
`config/exam_objectives.py` and `config/learn_content.py` for sourcing
notes.

## How grading works

Every task is validated in up to three layers:

1. **Artifacts** — the required files exist in your working directory and
   contain what was asked (static checks; always run).
2. **Execution** — the playbook passes `--syntax-check`, runs cleanly against
   *your* inventory with *your* `ansible.cfg`, and is **idempotent**
   (a second run must report `changed=0` — the exam's favorite trap).
3. **State** — ad-hoc queries against your managed nodes confirm the end
   state the playbook was supposed to produce.

## Quick start

```bash
# On the control node (needs ansible-core; ansible-navigator recommended)
git clone https://github.com/justbest23/rhce-simulator.git
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
  container one — SELinux-related task validation won't be meaningful under
  Docker (this is *also* true of rhcsa-simulator's containerized dev
  environment; see its CLAUDE.md). Firewalld mostly works but is less
  faithful than a real host's netfilter stack. If your session draws a lot
  of Domain-1/storage tasks and you want full fidelity, use real VMs
  instead (below).
  **Windows:** run `lab-setup.sh` and `rhce_simulator.py` from inside WSL2,
  not native PowerShell — Ansible's control node doesn't run natively on
  Windows. Docker Desktop's WSL2 backend makes `docker` work from a WSL
  prompt without extra setup.
* **Real lab (full fidelity):** point `RHCE_SIM_NODES` at one or more real
  RHEL 10 / Rocky 10 / Alma 10 VMs reachable over SSH instead of the Docker
  lab — needed if you want SELinux enforcement and firewalld to behave
  exactly like the exam. The first tasks in domain 1 walk you through key
  distribution and privilege escalation either way.

## Task catalog

31 tasks across 19 categories, mapped to the official page's own 11
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

Domain 1 (RHCSA foundation) has no dedicated category here by design —
that's the sibling rhcsa-simulator's job.

`python3 rhce_simulator.py --list-tasks` shows the live list.

## Running the test suite

```bash
python3 -m pytest -q
```

Unit tests mock the Ansible runner — they never require ansible-core,
managed nodes, or root.

## Roadmap

* Exam clock + timed mode parity with rhcsa-simulator
* More tasks per category (target ≥3 each)
* SM-2 spaced-repetition practice mode (port from rhcsa-simulator)
* Optional AI feedback on submitted playbooks via `ANTHROPIC_API_KEY`

## License

MIT
