"""
Base task class for all RHCE EX294 exam tasks.

Unlike the RHCSA simulator (which inspects local system state directly),
RHCE tasks grade three layers:

  1. artifact checks — the required file exists in the working directory
     and contains what the task asked for (static regex checks);
  2. execution checks — the playbook syntax-checks, runs clean against the
     candidate's own inventory, and is idempotent (second run changed=0);
  3. state checks — ad-hoc queries against managed nodes confirm the end
     state the playbook was supposed to produce.

All execution goes through validators.ansible_runner with cwd set to the
candidate's working directory, so THEIR ansible.cfg and inventory apply —
the same way the real exam grades results, not methods.
"""

import re
from abc import ABC, abstractmethod
from pathlib import Path

from config import settings
from core.validator import ValidationResult
from validators import ansible_runner as runner


class AnsibleTask(ABC):
    """Abstract base class for all RHCE exam tasks."""

    def __init__(self, id, category, difficulty="medium", points=None):
        self.id = id
        self.category = category
        self.difficulty = difficulty
        self.points = points or settings.DIFFICULTY_POINTS.get(difficulty, 20)
        self.description = ""
        self.hints = []
        self.exam_tips = []
        self.params = {}
        self.exam_domain = settings.CATEGORY_TO_DOMAIN.get(category, 0)

    # -- interface -----------------------------------------------------

    @abstractmethod
    def generate(self, **params):
        """Generate the task (randomize parameters). Returns self."""

    @abstractmethod
    def validate(self) -> ValidationResult:
        """Validate task completion against workdir + managed nodes."""

    # -- context -------------------------------------------------------

    @property
    def workdir(self) -> Path:
        return settings.get_workdir()

    @property
    def nodes(self) -> list:
        return settings.get_nodes()

    def result(self) -> ValidationResult:
        return ValidationResult(task_id=self.id, max_score=self.points)

    # -- artifact checks -----------------------------------------------

    def check_exists(self, res: ValidationResult, relpath: str) -> bool:
        path = self.workdir / relpath
        ok = path.exists()
        res.add(f"{relpath} exists", ok,
                "" if ok else f"expected at {path}")
        return ok

    def check_contains(self, res: ValidationResult, relpath: str,
                       pattern: str, name: str) -> bool:
        """Regex-search a workdir file (case-insensitive, multiline)."""
        path = self.workdir / relpath
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            res.add(name, False, f"{relpath} not readable")
            return False
        ok = re.search(pattern, text, re.IGNORECASE | re.MULTILINE) is not None
        res.add(name, ok, "" if ok else f"pattern not found in {relpath}: {pattern}")
        return ok

    # -- execution checks ----------------------------------------------

    def check_playbook_runs(self, res: ValidationResult, relpath: str,
                            require_idempotent: bool = True,
                            extra_args=None) -> bool:
        """Layer-2 checks: syntax, clean run, idempotence."""
        if not self.check_exists(res, relpath):
            return False
        if not runner.have_ansible():
            res.add(f"{relpath} executes", False,
                    "ansible-playbook not found on this control node")
            return False
        outcome = runner.full_playbook_check(self.workdir / relpath, self.workdir,
                                             extra_args=extra_args)
        res.add(f"{relpath} passes --syntax-check", outcome.syntax_ok, outcome.detail
                if not outcome.syntax_ok else "")
        if not outcome.syntax_ok:
            return False
        res.add(f"{relpath} runs without failures", outcome.run_ok,
                "" if outcome.run_ok else outcome.detail)
        if not outcome.run_ok:
            return False
        if require_idempotent:
            res.add(f"{relpath} is idempotent (2nd run changed=0)",
                    outcome.idempotent,
                    "" if outcome.idempotent else outcome.detail)
        return outcome.run_ok

    # -- state checks ----------------------------------------------------

    def check_node_state(self, res: ValidationResult, name: str, pattern: str,
                         module: str, args: str = "", expect: str = "",
                         become: bool = False) -> bool:
        """Ad-hoc query against the candidate's inventory; pass when the
        output matches `expect` (regex) and the command succeeds."""
        if not runner.have_ansible():
            res.add(name, False, "ansible not found on this control node")
            return False
        out = runner.adhoc(pattern, module, args, workdir=self.workdir,
                           become=become)
        ok = out.ok and (re.search(expect, out.text, re.MULTILINE) is not None
                         if expect else True)
        res.add(name, ok, "" if ok else _snip(out.text))
        return ok

    # -- display ---------------------------------------------------------

    def get_category_display_name(self) -> str:
        return settings.CATEGORY_DISPLAY.get(self.category, self.category)

    def get_domain_display(self) -> str:
        return settings.EXAM_DOMAINS.get(self.exam_domain, "Unknown")

    def __repr__(self):
        return (f"<Task {self.id}: {self.category} "
                f"({self.difficulty}, {self.points}pts, D{self.exam_domain})>")


def _snip(text: str, lines: int = 8) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])
