# RHCE Exam Simulator

RHCE **EX294 (RHEL 10)** exam simulator — a command-line trainer for the Red Hat
Certified Engineer exam. Presents exam-style Ansible automation tasks, then
grades them the way the real exam does: **by results, not methods** — it runs
your playbooks against your own inventory and inspects the state they produce
on your managed nodes.

Sibling project to [rhcsa-simulator](https://github.com/justbest23/rhcsa-simulator)
(RHCSA EX200 v10), sharing its conventions: Python standard library only,
task auto-discovery, SQLite progress tracking.

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
python3 rhce_simulator.py --exam              # full 4-hour-style exam (15 tasks)
python3 rhce_simulator.py --practice vault    # drill one category
python3 rhce_simulator.py --list-tasks        # catalog overview
python3 rhce_simulator.py --learn             # official EX294 objectives
python3 rhce_simulator.py --history           # past sessions & weak categories
```

Inside a session: type a task number to read it, do the work **in another
terminal**, then `v <n>` to validate it (`h <n>` for hints, `q` to finish).

## Lab setup

| Env var | Default | Meaning |
|---|---|---|
| `RHCE_SIM_WORKDIR` | `~/ansible` | Your Ansible working directory (ansible.cfg, inventory, playbooks) |
| `RHCE_SIM_NODES` | `localhost` | Comma-separated managed nodes used in task wording and state checks |
| `RHCE_SIM_REMOTE_USER` | `devops` | Remote user referenced by tasks |

* **Single machine:** the default works — put `localhost ansible_connection=local`
  in your inventory. Playbooks then configure the control node itself, so use a
  VM you can trash.
* **Real lab (recommended):** point `RHCE_SIM_NODES` at one or more RHEL 10 /
  Rocky 10 / Alma 10 VMs reachable over SSH; the first tasks in domain 1 walk
  you through key distribution and privilege escalation, matching the real
  exam flow.

## Task catalog

29 tasks across 17 categories covering all seven EX294 objective domains:
Ansible/navigator configuration, inventories, ad-hoc commands, content
navigator + execution environments, playbook authoring, variables & facts,
loops & conditionals, handlers & block/rescue, Jinja2 templates, file content
& archiving, roles, RHEL system roles, collections, Vault, and automated
storage / users / scheduling administration.

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
