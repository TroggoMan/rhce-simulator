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

Writing a task description
--------------------------
The description is the exam question, so it reads like one: it states the
required end state and nothing else. Real EX294 wording is flat and
declarative, and practising against something chattier is practising for
the wrong thing — on exam day nobody tells you which detail is the point.

  * Name files by absolute path the first time they appear
    ("Create a playbook /home/user/ansible/x.yml"), not as "x.yml in your
    working directory (...)".
  * No teaching in the description — but don't throw it away either. An
    aside like "(that is what handlers are for)" moves to `exam_tips`,
    printed by the engine's post-grading debrief; a "how do I even start"
    nudge moves to `hints`, shown on request during the task. Concept-level
    material for a whole category belongs in config/learn_content.py,
    which is what --learn browses. The candidate still gets all of it,
    just never mixed into the question.
  * No grading commentary. "that's what's graded", "this part isn't
    graded" and "don't chase changed=0 here" tell the candidate where to
    stop thinking. If a check doesn't apply, just don't ask for it.
  * State requirements as requirements: "The playbook must be idempotent"
    rather than "Idempotent (graders re-run playbooks)".
  * Reserve capitals for genuine ambiguity — ALL managed nodes vs. one, a
    SINGLE task vs. several. Everything shouting means nothing does.
"""

import re
from abc import ABC, abstractmethod
from pathlib import Path

from config import settings
from core.validator import ValidationResult
from validators import ansible_runner as runner

ENFORCEMENT_UNAVAILABLE = (
    "This lab's nodes have the real SELinux policy store but no live "
    "kernel enforcement, so the rule you created was graded — but its "
    "EFFECT can't be observed here.\n"
    "restorecon needs a kernel to write labels through; without one "
    "`ls -Z` reports no label at all, so this check would fail a correct "
    "answer rather than catch a wrong one. Containers share the host "
    "kernel and never get their own. To grade relabelling end to end, "
    "point RHCE_SIM_NODES at the VM lab (scripts/vm-lab-setup.sh)."
)

SELINUX_UNAVAILABLE = (
    "This lab's managed nodes have no live SELinux subsystem (no "
    "/sys/fs/selinux), so the playbook cannot be run or its effect "
    "observed here — your file was still graded on content above.\n"
    "SELinux is a host-kernel feature: containers share the host kernel "
    "and never get their own, so the Docker lab can't do this no matter "
    "how it's configured. To grade these fully, point RHCE_SIM_NODES at a "
    "real RHEL/Rocky/Alma 10 VM with SELinux enabled."
)


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
        self._probe_cache = {}

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

    # Whole-line comments only. An inline "# ..." can't be stripped safely
    # without a YAML parser — `content: "a # b"` is data, not a comment —
    # and a leading-# line is where a candidate's prose actually lands.
    _COMMENT_LINE = re.compile(r"^[ \t]*#.*$", re.MULTILINE)

    @classmethod
    def strip_comments(cls, text: str) -> str:
        """Blank out whole-line comments, keeping line count and offsets.

        Artifact checks look for what the candidate WROTE, and a comment is
        prose about the answer, not the answer. Without this a file whose
        comment happens to quote the required syntax ("# the variable is
        timesync_ntp_servers") passes a check its actual code fails.
        """
        return cls._COMMENT_LINE.sub("", text)

    def read_artifact(self, relpath: str) -> str:
        """Workdir file with comments stripped, or "" if unreadable."""
        try:
            text = (self.workdir / relpath).read_text(
                encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return self.strip_comments(text)

    def check_contains(self, res: ValidationResult, relpath: str,
                       pattern: str, name: str) -> bool:
        """Regex-search a workdir file (case-insensitive, multiline).

        Comments are stripped first — see strip_comments().
        """
        path = self.workdir / relpath
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            res.add(name, False, f"{relpath} not readable")
            return False
        text = self.strip_comments(text)
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

    # -- environment probes ----------------------------------------------
    #
    # Probes ask "can this lab even demonstrate the thing?" They are never
    # scored — their answer decides whether a check is graded or recorded
    # as skipped. Results are cached per task instance so a single
    # validate() doesn't re-run the same ad-hoc query repeatedly.

    def probe(self, module: str, args: str = "", expect: str = "",
              become: bool = False, pattern: str = "all",
              require_all: bool = True) -> bool:
        """Cheap yes/no question about the managed nodes. Never scored.

        require_all=True  — every targeted host must succeed.
        require_all=False — ANY host succeeding is enough. Needed whenever
            the thing being probed is legitimately present on only some
            hosts (a spare disk, say): `ansible all` exits non-zero if a
            single host fails, so an rc-based test would answer "no" even
            though the resource exists somewhere.
        """
        if not runner.have_ansible():
            return False
        key = (pattern, module, args, expect, become, require_all)
        if key in self._probe_cache:
            return self._probe_cache[key]
        out = runner.adhoc(pattern, module, args, workdir=self.workdir,
                           become=become)
        if require_all:
            ok = out.ok and (re.search(expect, out.text, re.MULTILINE) is not None
                             if expect else True)
        else:
            # Per-host result lines look like "jerry | CHANGED | rc=0 >>".
            ok = re.search(expect if expect else r"\|\s*(SUCCESS|CHANGED)",
                           out.text, re.MULTILINE) is not None
        self._probe_cache[key] = ok
        return ok

    def selinux_available(self) -> bool:
        """True if SELinux work can be graded on these nodes at all.

        Two ways that's true, and the distinction matters less than it
        looks. A VM has a live subsystem: /sys/fs/selinux exists because
        the running kernel initialized SELinux. A container never can —
        it shares the host kernel and gets no selinuxfs of its own — but
        the Docker lab installs the real targeted policy store, and
        libsemanage manipulates that store for real with no kernel
        involved. Booleans, port types and file contexts are genuine
        there; a name policy doesn't define is rejected by policy.

        So both are gradeable, and the check is "is there something to
        grade", not "is there a kernel". What the container CANNOT do is
        enforcement — see docker/selinux-sim/rhce_selinux_sim.py, and
        enforcement_real() below for the checks that still have to skip.
        """
        return (self.probe("ansible.builtin.command", "test -d /sys/fs/selinux",
                           become=True)
                or self.probe("ansible.builtin.command",
                              "test -d /var/lib/selinux/targeted", become=True))

    def enforcement_real(self) -> bool:
        """True only where SELinux is genuinely enforcing in a live kernel.

        The narrower question. Anything that grades an EFFECT of
        enforcement — a denial, a relabel actually taking hold — needs
        this, not selinux_available(); the simulated nodes will happily
        report the right on-disk state for work whose runtime half never
        happened.
        """
        return self.probe("ansible.builtin.command", "test -d /sys/fs/selinux",
                          become=True)

    def skip_without_enforcement(self, res: ValidationResult, what: str) -> bool:
        """Skip `what` unless SELinux is genuinely enforcing in a kernel.

        For checks that grade an EFFECT rather than a stored rule. The
        simulated nodes record an fcontext rule perfectly well — that part
        is real and still graded — but restorecon has no kernel to write
        labels through, so `ls -Z` reports "?" and a correct answer would
        fail. Skipping is honest here; passing it would not be.
        """
        if self.enforcement_real():
            return False
        res.add_skip(what, ENFORCEMENT_UNAVAILABLE)
        return True

    def skip_without_selinux(self, res: ValidationResult, what: str) -> bool:
        """Record `what` as skipped when the lab has no SELinux. Returns
        True when it skipped (caller should stop)."""
        if self.selinux_available():
            return False
        res.add_skip(what, SELINUX_UNAVAILABLE)
        return True

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
