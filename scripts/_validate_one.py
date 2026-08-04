#!/usr/bin/env python3
"""Validate a single task by id, for spot-checking without a session.

    python3 scripts/_validate_one.py <task_id> [key=value ...]

Generate params can be pinned so a randomised task grades against the
same values twice (the interactive session holds one instance; this does
not).
"""
import sys
from pathlib import Path

# Runnable as scripts/_validate_one.py from the repo root, so the repo
# itself has to be importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.registry import TaskRegistry
import tasks  # noqa: F401  (import triggers task auto-discovery)

if len(sys.argv) < 2:
    sys.exit(__doc__)

task_id = sys.argv[1]
params = dict(arg.split("=", 1) for arg in sys.argv[2:] if "=" in arg)

by_id = {cls().id: cls
         for category in TaskRegistry.get_all_categories()
         for cls in TaskRegistry.get_tasks_by_category(category)}
if task_id not in by_id:
    sys.exit(f"unknown task id: {task_id}")

result = by_id[task_id]().generate(**params).validate()
for check in result.checks:
    mark = "SKIP" if check.skipped else ("PASS" if check.passed else "FAIL")
    print(f"  [{mark}] {check.name}")
    if check.detail and not check.passed:
        print(f"         {check.detail.strip().splitlines()[0][:110]}")
print(f"  -> {result.score}/{result.max_score}")
