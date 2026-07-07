"""
Validation result types shared by all tasks.

A task's validate() returns a ValidationResult made of individual
CheckResults. A task passes only if every check passes; the score is
proportional so partially-correct work still earns partial credit in
practice modes (the real exam grades per-item criteria the same way).
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ValidationResult:
    task_id: str
    max_score: int
    checks: List[CheckResult] = field(default_factory=list)
    error_message: str = ""

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)

    @property
    def score(self) -> int:
        if not self.checks:
            return 0
        good = sum(1 for c in self.checks if c.passed)
        return round(self.max_score * good / len(self.checks))

    def add(self, name: str, passed: bool, detail: str = "") -> "ValidationResult":
        self.checks.append(CheckResult(name, bool(passed), detail))
        return self
