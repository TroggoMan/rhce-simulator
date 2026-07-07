# RHCE Exam Simulator

RHCE EX294 (RHEL 10) exam simulator. Presents Ansible automation tasks and
grades them by running the candidate's playbooks and checking resulting node
state. Sibling to rhcsa-simulator — same conventions.

## Commands

```bash
python3 rhce_simulator.py --quick|--exam|--practice CAT|--list-tasks|--learn|--history
python3 -m pytest -q            # test suite (no Ansible needed — runner is mocked)
```

## Architecture

- `rhce_simulator.py` — CLI entry point
- `config/settings.py` — categories → exam domains, paths, env vars
- `core/` — registry (auto-discovery), engine (interactive session), results_db (SQLite), validator (ValidationResult/CheckResult)
- `tasks/` — one module per topic; classes register via `@TaskRegistry.register("<category>")` and subclass `tasks/base.py:AnsibleTask`
- `validators/ansible_runner.py` — the ONLY place subprocesses run: syntax check, playbook run, idempotence re-run, ad-hoc state queries

## Key conventions

- **Python standard library only.** No PyYAML — YAML validity is checked via
  `ansible-playbook --syntax-check`, static content via regex.
- Validation layers: artifact (static, always) → execution (needs
  ansible-core) → node state (ad-hoc against the candidate's own inventory).
  Every layer degrades gracefully with a clear failure detail; validators
  must never raise.
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
