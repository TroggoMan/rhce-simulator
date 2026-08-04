# RHCE Exam Simulator

RHCE EX294 (RHEL 10) exam simulator. Presents Ansible automation tasks and
grades them by running the candidate's playbooks and checking resulting node
state. Sibling to rhcsa-simulator — same conventions.

## Commands

```bash
python3 rhce_simulator.py --quick|--exam|--practice CAT|--focus|--list-tasks|--learn|--history|--reset-progress
python3 -m pytest -q            # test suite (no Ansible needed — runner is mocked)
./scripts/lab-reset.sh          # fast node-state reset (Docker recreate / Vagrant snapshot restore)
```

`--focus` picks a practice session weighted toward the candidate's own
weakest categories (`ResultsDB.weak_categories`, worst-first, never-
attempted categories rank weakest of all). `--reset-progress` wipes the
SQLite history that both `--history` and `--focus` read from.

**Lab bootstrap is intentionally NOT automated.** `scripts/lab-setup.sh`
and `scripts/vm-lab-setup.sh` provision nodes with exam-style bootstrap
access only (root/password, `RHCE_LAB_ROOT_PASSWORD`) — no automation
user, no SSH key, no inventory file. That gap is deliberate: building an
inventory/ansible.cfg/automation user/key from root+password access is
literally task 1 on the real exam, and having the lab script do it for
the candidate would make the `ansible_config`/`inventory`/`managed_nodes`
categories trivially already-solved. Don't "fix" this by writing an
inventory automatically — see `rhce_simulator.py:warn_if_no_inventory()`
and `config/learn_content.py`'s `managed_nodes` entry for how the gap is
taught instead.

## Architecture

- `rhce_simulator.py` — CLI entry point
- `config/settings.py` — categories → exam domains (11 domains, matching the
  official page exactly as of 2026-07-23), paths, env vars
- `config/exam_objectives.py` — official objective bullets, with sourcing notes
- `config/learn_content.py` — actual study content per category (explanation,
  module syntax/examples, common mistakes, exam tips), consumed by `core/learn.py`
- `core/` — registry (auto-discovery), engine (interactive session), learn
  (interactive --learn browser), results_db (SQLite), validator (ValidationResult/CheckResult)
- `tasks/` — one module per topic; classes register via `@TaskRegistry.register("<category>")` and subclass `tasks/base.py:AnsibleTask`
- `validators/ansible_runner.py` — the ONLY place subprocesses run: syntax check, playbook run, idempotence re-run, ad-hoc state queries

## Key conventions

- **Python standard library only.** No PyYAML — YAML validity is checked via
  `ansible-playbook --syntax-check`, static content via regex.
- Validation layers: artifact (static, always) → execution (needs
  ansible-core) → node state (ad-hoc against the candidate's own inventory).
  Every layer degrades gracefully with a clear failure detail; validators
  must never raise.
- **Skipped checks** (`ValidationResult.add_skip`) are for things the LAB
  cannot observe, never for things the candidate got wrong. They're excluded
  from `passed` and from the score denominator, so a correct answer isn't
  penalised on a lab that can't look. Decide via `AnsibleTask.probe(...)` /
  `selinux_available()` — cheap ad-hoc queries that are never themselves
  scored. Used by the SELinux tasks (no selinuxfs in containers), the
  network system-role task (no NetworkManager) and the raw-disk storage
  task (no spare disk). Always grade the artifact layer first so a wrong
  playbook still fails on a limited lab.
- All execution uses `cwd=workdir` so the candidate's own ansible.cfg and
  inventory apply. Never pass `-i` or override their config.
- Tasks randomize parameters in `generate(**params)`; accept explicit params
  for testability. Descriptions use exam-style wording.
- A task passes only if ALL checks pass; score is proportional (partial credit).
- Unit tests monkeypatch `validators.ansible_runner.run` (see
  tests/unit/test_ansible_runner.py) and the `workdir`/`no_ansible` fixtures
  in tests/conftest.py. Tests must never require Ansible, nodes, or root.

## Testing caveat

This dev container has no Ansible or managed nodes. Only the static layer can
be exercised for real here; execution/state layers are covered by mocked
tests. For live testing use a RHEL/Rocky/Alma 10 VM with ansible-core.
