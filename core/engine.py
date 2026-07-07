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
from utils import formatters as fmt


class Session:
    def __init__(self, mode: str, category: str = None, count: int = None,
                 db: ResultsDB = None):
        self.mode = mode
        counts = {"quick": settings.QUICK_TASK_COUNT,
                  "exam": settings.EXAM_TASK_COUNT}
        self.count = count or counts.get(mode, settings.QUICK_TASK_COUNT)
        self.tasks = TaskRegistry.get_random_tasks(self.count, category=category)
        self.results = {}
        self.db = db or ResultsDB()

    # -- rendering -------------------------------------------------------

    def show_overview(self):
        print(fmt.banner(f"{settings.EXAM_NAME} — {self.mode} session"))
        print(fmt.dim(f"Working directory: {settings.get_workdir()}  "
                      f"| managed nodes: {', '.join(settings.get_nodes())}"))
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
            line = fmt.ok(check.name) if check.passed else fmt.fail(check.name)
            print("  " + line)
            if check.detail and not check.passed:
                for detail_line in check.detail.splitlines():
                    print(fmt.dim(f"      {detail_line}"))
        print(f"  → {result.score}/{result.max_score} pts\n")

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
        print(fmt.score_line(score, max_score, settings.PASS_PERCENT))

    # -- loop ---------------------------------------------------------------

    HELP = ("commands:  <n> show task n | h <n> hints | v <n> validate n | "
            "V validate all | l list | q finish & quit")

    def run(self):  # pragma: no cover - interactive loop
        self.show_overview()
        print(fmt.dim(self.HELP))
        while True:
            try:
                raw = input(f"{C.BOLD}rhce>{C.RESET} ").strip()
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
            elif cmd in ("h", "v") or cmd.isdigit():
                sel = cmd if cmd.isdigit() else arg
                if not sel.isdigit() or not 1 <= int(sel) <= len(self.tasks):
                    print(fmt.warn(f"pick a task number 1-{len(self.tasks)}"))
                    continue
                idx = int(sel) - 1
                if cmd == "h":
                    self.show_hints(idx)
                elif cmd == "v":
                    self.validate_task(idx)
                else:
                    self.show_task(idx)
            else:
                print(fmt.dim(self.HELP))
        self.finish()
