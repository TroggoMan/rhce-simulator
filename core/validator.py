"""
Validation result types shared by all tasks.

A task's validate() returns a ValidationResult made of individual
CheckResults. A task passes only if every check passes; the score is
proportional so partially-correct work still earns partial credit in
practice modes (the real exam grades per-item criteria the same way).

Some checks can't be run at all in certain labs — the clearest case is
SELinux, which is a host-kernel feature and simply does not exist inside a
container no matter how the container is configured. Marking those checks
SKIPPED (rather than failed) keeps a correct answer from being scored as
wrong just because the lab can't observe it: skipped checks are excluded
from both the pass decision and the score denominator, and are reported to
the candidate with the reason so the limitation is never silent.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    skipped: bool = False


@dataclass
class ValidationResult:
    task_id: str
    max_score: int
    checks: List[CheckResult] = field(default_factory=list)
    error_message: str = ""

    @property
    def gradeable(self) -> List[CheckResult]:
        """Checks that actually counted — skipped ones are not graded."""
        return [c for c in self.checks if not c.skipped]

    @property
    def skipped(self) -> List[CheckResult]:
        return [c for c in self.checks if c.skipped]

    @property
    def passed(self) -> bool:
        gradeable = self.gradeable
        return bool(gradeable) and all(c.passed for c in gradeable)

    @property
    def score(self) -> int:
        gradeable = self.gradeable
        if not gradeable:
            return 0
        good = sum(1 for c in gradeable if c.passed)
        return round(self.max_score * good / len(gradeable))

    def add(self, name: str, passed: bool, detail: str = "") -> "ValidationResult":
        self.checks.append(CheckResult(name, bool(passed), detail))
        return self

    def add_skip(self, name: str, reason: str) -> "ValidationResult":
        """Record a check the lab environment cannot evaluate.

        Neither passes nor fails: excluded from `passed` and from the score
        denominator, but still shown to the candidate with `reason`.
        """
        self.checks.append(CheckResult(name, False, reason, skipped=True))
        return self
