"""
Interactive session loop for quick / practice / exam modes.

The workflow mirrors the real exam: the simulator presents numbered tasks,
the candidate does the actual work in another terminal (in their Ansible
working directory), then asks the simulator to validate. Validation runs
the candidate's playbooks for real — expect it to take a few seconds per
task, longer with slow managed nodes.
"""

from config import settings
from config.settings import C
from core.registry import TaskRegistry
from core.results_db import ResultsDB
from core.timer import ExamClock
from utils import formatters as fmt


class Session:
    def __init__(self, mode: str, category: str = None, categories: list = None,
                 count: int = None, db: ResultsDB = None, timed: bool = None):
        self.mode = mode
        counts = {"quick": settings.QUICK_TASK_COUNT,
                  "exam": settings.EXAM_TASK_COUNT,
                  "focus": settings.QUICK_TASK_COUNT}
        self.count = count or counts.get(mode, settings.QUICK_TASK_COUNT)
        self.tasks = TaskRegistry.get_random_tasks(
            self.count, category=category, categories=categories)
        self.results = {}
        self.db = db or ResultsDB()
        # Only the full exam is timed by default — drilling one category
        # against a 4-hour clock would be meaningless.
        if timed is None:
            timed = mode == "exam"
        self.clock = (ExamClock(settings.EXAM_DURATION_MINUTES)
                      if timed else None)

    # -- rendering -------------------------------------------------------

    def show_overview(self):
        print(fmt.banner(f"{settings.EXAM_NAME} — {self.mode} session"))
        print(fmt.dim(f"Working directory: {settings.get_workdir()}  "
                      f"| managed nodes: {', '.join(settings.get_nodes())}"))
        if self.clock:
            print(fmt.dim(
                f"Exam clock: {settings.EXAM_DURATION_MINUTES} minutes. It "
                f"warns but never cuts you off — overrunning is data, not a "
                f"failure state."))
        print(fmt.dim("Do the work in another terminal, then validate here.\n"))
        for i, task in enumerate(self.tasks, 1):
            mark = " "
            if task.id in self.results:
                mark = ("✔" if self.results[task.id].passed else "✘")
            print(f"  {mark} {i:2}. [{task.get_category_display_name()}] "
                  f"{task.points} pts")

    def show_task(self, idx: int):
        task = self.tasks[idx]
        print(fmt.banner(f"Task {idx + 1} of {len(self.tasks)} — "
                         f"{task.get_category_display_name()} ({task.points} pts)"))
        print(task.description.strip() + "\n")

    def show_hints(self, idx: int):
        task = self.tasks[idx]
        if not task.hints:
            print(fmt.warn("No hints for this task."))
        for hint in task.hints:
            print(f"  {C.YELLOW}💡 {hint}{C.RESET}")

    # -- validation --------------------------------------------------------

    def validate_task(self, idx: int):
        task = self.tasks[idx]
        print(fmt.dim(f"Validating {task.id} (runs your playbooks for real)…"))
        result = task.validate()
        self.results[task.id] = result
        for check in result.checks:
            if check.skipped:
                line = fmt.skip(f"{check.name}  (not graded here)")
            else:
                line = fmt.ok(check.name) if check.passed else fmt.fail(check.name)
            print("  " + line)
            if check.detail and not check.passed:
                for detail_line in check.detail.splitlines():
                    print(fmt.dim(f"      {detail_line}"))
        if result.skipped:
            print(fmt.dim(f"      ({len(result.skipped)} check(s) skipped — "
                          f"scored out of the rest)"))
        print(f"  → {result.score}/{result.max_score} pts\n")

    # -- disputes ----------------------------------------------------------

    def dispute_task(self, idx: int):  # pragma: no cover - interactive
        """File a checker dispute for a task the candidate believes was
        scored wrongly. Read-only: gathers evidence, never changes state."""
        from core import dispute

        task = self.tasks[idx]
        result = self.results.get(task.id)
        if result is None:
            print(fmt.warn(f"Validate task {idx + 1} first — a dispute needs "
                           f"a result to argue about (v {idx + 1})."))
            return

        failed = [c for c in result.checks if not c.passed and not c.skipped]
        print(fmt.banner(f"Dispute checker for {task.id}"))
        if failed:
            print("Checks that failed:")
            for check in failed:
                print(f"  {fmt.fail(check.name)}")
        else:
            print(fmt.warn("Nothing failed on this task — you can still file "
                           "a dispute (e.g. it passed but shouldn't have)."))
        print(fmt.dim(
            "\nSay what you think the checker got wrong and why your answer "
            "is correct. Be specific: name the module/option you used and "
            "what you expected the check to accept. Finish with an empty "
            "line.\n"))

        lines = []
        while True:
            try:
                line = input("  ")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line.strip():
                break
            lines.append(line)
        argument = "\n".join(lines).strip()
        if not argument:
            print(fmt.dim("No argument written — dispute cancelled."))
            return

        extra = input(fmt.dim(
            "Extra command(s) to capture as evidence, ';;'-separated "
            "(optional, Enter to skip): ")).strip()
        extra_commands = [c for c in extra.split(";;") if c.strip()] if extra else []

        print(fmt.dim("\nCollecting evidence (read-only)…"))
        artifacts = dispute.collect_artifacts(task)
        evidence = dispute.collect_evidence(task.category, extra_commands)
        body = dispute.build_report(task, result, argument, artifacts, evidence)
        path = dispute.save_report(task, body)
        print(fmt.ok(f"Report saved: {path}"))

        if not dispute.gh_available():
            print(fmt.warn(
                "gh CLI not installed or not authenticated, so the issue "
                "can't be opened from here."))
            print("Open this URL on a machine where you're logged into "
                  "GitHub, then click Submit:\n")
            print(dispute.issue_url(task, body))
            return

        if input("File this as a GitHub issue now? [y/N] ").strip().lower() \
                not in ("y", "yes"):
            print(fmt.dim("Not submitted — the saved report is still there."))
            return

        ok, message = dispute.submit_issue(task, path)
        if ok:
            print(fmt.ok(f"Filed: {message}"))
            print(fmt.dim("An AI reviewer will inspect the checker against "
                          "your evidence and comment a verdict on the issue."))
        else:
            print(fmt.fail("Could not file the issue:"))
            for line in message.splitlines():
                print(fmt.dim(f"    {line}"))
            print("\nFallback — open this URL and click Submit:\n")
            print(dispute.issue_url(task, body))

    def finish(self):
        score = sum(r.score for r in self.results.values())
        max_score = sum(t.points for t in self.tasks)
        session_id = self.db.start_session(self.mode)
        for task in self.tasks:
            if task.id in self.results:
                self.db.record_task(session_id, task, self.results[task.id])
        self.db.finish_session(session_id, score, max_score)
        print(fmt.banner("Session results"))
        for i, task in enumerate(self.tasks, 1):
            res = self.results.get(task.id)
            if res is None:
                print(f"  –  {i:2}. {task.id}  (not validated)  0/{task.points}")
            else:
                mark = "✔" if res.passed else "✘"
                print(f"  {mark}  {i:2}. {task.id}  {res.score}/{res.max_score}")
        print()
        if self.clock:
            print(fmt.dim(self.clock.summary()))
        print(fmt.score_line(score, max_score, settings.PASS_PERCENT))

    # -- loop ---------------------------------------------------------------

    HELP = ("commands:  <n> show task n | h <n> hints | v <n> validate n | "
            "V validate all | d <n> dispute n | l list | q finish & quit")

    def run(self):  # pragma: no cover - interactive loop
        self.show_overview()
        print(fmt.dim(self.HELP))
        while True:
            if self.clock:
                warning = self.clock.due_warning()
                if warning:
                    print(fmt.warn(warning))
            prompt = (f"{C.BOLD}rhce{C.RESET} [{self.clock.label()}]{C.BOLD}>{C.RESET} "
                      if self.clock else f"{C.BOLD}rhce>{C.RESET} ")
            try:
                raw = input(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not raw:
                continue
            cmd, _, arg = raw.partition(" ")
            if cmd == "q":
                break
            elif cmd == "l":
                self.show_overview()
            elif cmd == "V":
                for i in range(len(self.tasks)):
                    self.validate_task(i)
            elif cmd in ("h", "v", "d") or cmd.isdigit():
                sel = cmd if cmd.isdigit() else arg
                if not sel.isdigit() or not 1 <= int(sel) <= len(self.tasks):
                    print(fmt.warn(f"pick a task number 1-{len(self.tasks)}"))
                    continue
                idx = int(sel) - 1
                if cmd == "h":
                    self.show_hints(idx)
                elif cmd == "v":
                    self.validate_task(idx)
                elif cmd == "d":
                    self.dispute_task(idx)
                else:
                    self.show_task(idx)
            else:
                print(fmt.dim(self.HELP))
        self.finish()
