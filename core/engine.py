"""
Interactive session loop for quick / practice / exam modes.

The workflow mirrors the real exam: the simulator presents numbered tasks,
the candidate does the actual work in another terminal (in their Ansible
working directory), then asks the simulator to validate. Validation runs
the candidate's playbooks for real — expect it to take a few seconds per
task, longer with slow managed nodes.

A browser task panel (core/task_gui.py) mirrors this terminal: same task
list, plus it can submit for grading, dispute a result, and reset the lab
on its own. Because it drives real state — not just a read-only view — the
terminal's own input() has to stop blocking exclusively on keystrokes typed
here; see _read_command below for how that works without two threads
fighting over stdin.
"""

import queue
import threading
import time

from config import settings
from config.settings import C
from core.registry import TaskRegistry
from core.results_db import ResultsDB
from core.timer import ExamClock
from utils import formatters as fmt


class Session:
    def __init__(self, mode: str, category: str = None, categories: list = None,
                 count: int = None, db: ResultsDB = None, timed: bool = None,
                 gui: bool = True, gui_port: int = None, gui_bind: str = "0.0.0.0",
                 headless: bool = False):
        self.mode = mode
        # True for a --browser session: nothing is reading this process's
        # real terminal, so the input loop must never block on input() —
        # see _read_command. Panel-driven submit/quit are the only inputs.
        self.headless = headless
        counts = {"quick": settings.QUICK_TASK_COUNT,
                  "exam": settings.EXAM_TASK_COUNT,
                  "focus": settings.QUICK_TASK_COUNT,
                  "adaptive": settings.QUICK_TASK_COUNT}
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

        # -- browser task panel --------------------------------------------
        self.gui_enabled = gui
        self.gui_port = gui_port
        self.gui_bind = gui_bind
        self.panel = None
        self.controller = None
        # Shared with the panel so both views agree where the session is:
        # in_progress -> validating -> complete.
        self.panel_status = "in_progress"
        self.panel_results = None

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
        self.show_debrief(task)

    def show_debrief(self, task):
        """Teach AFTER grading, never inside the question.

        A task's exam_tips are the "why" behind it — the thing that bites
        people on exam day. Printing them here keeps the description
        itself as bare as a real exam item while the explanation still
        reaches the candidate, at the point where it means something
        because they've just seen whether they got it right.
        """
        if not task.exam_tips:
            return
        print(fmt.dim("  Worth knowing:"))
        for tip in task.exam_tips:
            print(fmt.dim(f"    • {tip}"))
        print()

    def validate_all(self):
        """Validate every task not yet graded. Shared by the 'V' command and
        a panel-driven submit, so there is exactly one grading path
        regardless of which button was pressed."""
        for i in range(len(self.tasks)):
            if self.tasks[i].id not in self.results:
                self.validate_task(i)
        self._sync_panel_results()

    # -- panel results -------------------------------------------------------

    def _sync_panel_results(self):
        """Flatten self.results into the shape the panel's JS renders.

        Kept separate from validate_task/validate_all's own printing: the
        terminal view and the panel view are driven from the same
        ValidationResult objects, just shaped differently for each.
        """
        score = sum(r.score for r in self.results.values())
        max_score = sum(t.points for t in self.tasks)
        percentage = round(100 * score / max_score, 1) if max_score else 0
        records = []
        for task in self.tasks:
            result = self.results.get(task.id)
            if result is None:
                continue
            records.append({
                "task_id": task.id,
                "category": task.get_category_display_name(),
                "description": task.description,
                "score": result.score,
                "max_score": result.max_score,
                "passed": bool(result.passed),
                "checks": [
                    {"name": c.name, "passed": bool(c.passed),
                     "skipped": bool(c.skipped), "message": c.detail or c.name}
                    for c in result.checks
                ],
            })
        self.panel_results = {
            "score": score, "max_score": max_score, "percentage": percentage,
            "passed": max_score > 0 and score / max_score >= settings.PASS_PERCENT / 100,
            "tasks": records,
        }
        if len(self.results) >= len(self.tasks):
            self.panel_status = "complete"

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

    # -- browser panel -------------------------------------------------------

    def _start_panel(self):  # pragma: no cover - network/thread side effects
        """Start the task panel, if enabled. Never fatal — a candidate must
        be able to run the whole simulator from a box with no free port and
        no browser at all."""
        if not self.gui_enabled:
            return
        try:
            from core import task_gui
            from core.panel_control import PanelController
        except Exception as e:
            print(fmt.warn(f"Task panel unavailable ({e}) — continuing in "
                           f"the terminal only."))
            return
        task_gui.clear_marks()
        self.controller = PanelController(self)
        port = self.gui_port or task_gui.DEFAULT_PORT
        self.panel, urls = task_gui.start_for_session(
            self, controller=self.controller, port=port, bind=self.gui_bind)
        if not urls:
            print(fmt.warn(f"Task panel could not bind port {port} — "
                           f"continuing in the terminal only. Try "
                           f"--gui <port> for a free one, or --no-gui."))
            self.controller = None
            return
        print(fmt.banner("Task panel"))
        for url in urls:
            print(f"  {url}")
        print(fmt.dim("  Open one of these in a browser window beside your "
                      "terminal. It can submit for grading, dispute a "
                      "result and reset the lab on its own.\n"))

    def _stop_panel(self):
        if self.panel:
            self.panel.stop()
            self.panel = None
        self.controller = None

    # -- input --------------------------------------------------------------
    # A single background reader owns stdin for the whole session — NOT one
    # thread per prompt. Spawning a fresh input() thread every loop
    # iteration would leave the previous one still blocked on stdin the
    # instant a panel submit interrupts the wait, and two threads racing to
    # read the same terminal is exactly the kind of intermittent, hard-to-
    # reproduce bug worth designing away rather than risking.

    def _ensure_reader(self):
        if getattr(self, "_input_q", None) is not None:
            return
        self._input_q = queue.Queue()

        def _reader():
            while True:
                try:
                    line = input()
                except (EOFError, KeyboardInterrupt):
                    self._input_q.put(None)  # sentinel: terminal is done
                    return
                self._input_q.put(line)

        threading.Thread(target=_reader, daemon=True, name="rhce-stdin").start()

    def _read_command(self, prompt: str):
        """Block for a terminal command, but return '__submit__'/'__quit__'
        early if the panel requests one first. Returns None on EOF/Ctrl-C.

        Headless (--browser) sessions skip real stdin entirely — this
        process's terminal, if it even has one, isn't what's driving the
        session, and treating its EOF as "candidate quit" would end the
        session the instant a non-interactive stdin (a service, a
        background job) hit it. The panel is the only input source."""
        if self.headless:
            print(prompt)
            while True:
                if self.controller and self.controller.submit_requested.is_set():
                    self.controller.submit_requested.clear()
                    return "__submit__"
                if self.controller and self.controller.quit_requested.is_set():
                    self.controller.quit_requested.clear()
                    return "__quit__"
                time.sleep(0.2)
        self._ensure_reader()
        print(prompt, end="", flush=True)
        while True:
            if self.controller and self.controller.submit_requested.is_set():
                self.controller.submit_requested.clear()
                print()  # the prompt is still on-screen with no newline
                return "__submit__"
            if self.controller and self.controller.quit_requested.is_set():
                self.controller.quit_requested.clear()
                print()
                return "__quit__"
            try:
                return self._input_q.get(timeout=0.2)
            except queue.Empty:
                continue

    # -- loop ---------------------------------------------------------------

    HELP = ("commands:  <n> show task n | h <n> hints | v <n> validate n | "
            "V validate all | d <n> dispute n | l list | q finish & quit")

    def run(self):  # pragma: no cover - interactive loop
        self.show_overview()
        print(fmt.dim(self.HELP))
        self._start_panel()
        try:
            while True:
                if self.clock:
                    warning = self.clock.due_warning()
                    if warning:
                        print(fmt.warn(warning))
                prompt = (f"{C.BOLD}rhce{C.RESET} [{self.clock.label()}]"
                          f"{C.BOLD}>{C.RESET} " if self.clock
                          else f"{C.BOLD}rhce>{C.RESET} ")
                raw = self._read_command(prompt)
                if raw is None:
                    print()
                    break
                if raw == "__quit__":
                    print(fmt.dim("Quit from the task panel."))
                    break
                if raw == "__submit__":
                    print(fmt.dim("Submitted from the task panel — "
                                  "validating…"))
                    self.validate_all()
                    continue
                raw = raw.strip()
                if not raw:
                    continue
                cmd, _, arg = raw.partition(" ")
                if cmd == "q":
                    break
                elif cmd == "l":
                    self.show_overview()
                elif cmd == "V":
                    self.validate_all()
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
                        self._sync_panel_results()
                    elif cmd == "d":
                        self.dispute_task(idx)
                    else:
                        self.show_task(idx)
                else:
                    print(fmt.dim(self.HELP))
        finally:
            self._stop_panel()
        self.finish()

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
