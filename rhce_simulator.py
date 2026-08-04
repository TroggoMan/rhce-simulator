#!/usr/bin/env python3
"""
RHCE EX294 (RHEL 10) Exam Simulator — main entry point.

Sibling project to rhcsa-simulator. Presents exam-style Ansible automation
tasks, then grades them by running the candidate's own playbooks against
their own inventory and checking the resulting state on managed nodes.

Usage:
    python3 rhce_simulator.py --quick             # 5 random tasks
    python3 rhce_simulator.py --exam              # full exam (settings.EXAM_TASK_COUNT tasks)
    python3 rhce_simulator.py --practice roles    # drill one category
    python3 rhce_simulator.py --focus             # practice session weighted to your weakest categories
    python3 rhce_simulator.py --list-tasks        # catalog overview
    python3 rhce_simulator.py --learn             # browse domains -> topics -> study content
    python3 rhce_simulator.py --history           # past sessions
    python3 rhce_simulator.py --reset-progress    # clear tracked history (asks to confirm)

Environment:
    RHCE_SIM_WORKDIR      Ansible working dir (default ~/ansible)
    RHCE_SIM_NODES        comma-separated managed nodes (default localhost)
    RHCE_SIM_REMOTE_USER  remote user for task wording (default devops)
"""

import argparse
import sys

from config import settings
from config.settings import C
from utils import formatters as fmt


def cmd_list_tasks():
    from core.registry import TaskRegistry
    print(fmt.banner(f"{settings.EXAM_NAME} — task catalog"))
    total = 0
    for cat in TaskRegistry.get_all_categories():
        classes = TaskRegistry.get_tasks_by_category(cat)
        total += len(classes)
        domain = settings.CATEGORY_TO_DOMAIN.get(cat, 0)
        print(f"{C.BOLD}{settings.CATEGORY_DISPLAY.get(cat, cat)}{C.RESET} "
              f"{fmt.dim(f'(domain {domain}, {len(classes)} tasks)')}")
        for tc in classes:
            inst = tc().generate()
            first_line = inst.description.strip().splitlines()[0]
            print(f"    {inst.id:<24} {inst.difficulty:<7} {first_line[:70]}")
    print(f"\n{C.BOLD}Total: {total} tasks{C.RESET}")


def cmd_learn():  # pragma: no cover - interactive loop
    from core import learn
    learn.run()


def cmd_history():
    from core.results_db import ResultsDB
    db = ResultsDB()
    rows = db.history()
    print(fmt.banner("Session history"))
    if not rows:
        print("No completed sessions yet.")
    for sid, mode, started, score, max_score in rows:
        pct = round(100 * score / max_score) if max_score else 0
        print(f"  #{sid:<4} {mode:<9} {started}  {score}/{max_score} ({pct}%)")
    stats = db.category_stats()
    if stats:
        print(f"\n{C.BOLD}Per-category pass rate:{C.RESET}")
        for cat, attempts, passes in stats:
            display = settings.CATEGORY_DISPLAY.get(cat, cat)
            print(f"  {display:<38} {passes or 0}/{attempts}")
    db.close()


def warn_if_no_inventory(category: str = None):
    """The lab scripts deliberately hand you bootstrap-only access (root +
    password), not a working inventory — see scripts/lab-setup.sh and
    scripts/vm-lab-setup.sh. Nothing else in this simulator can run until
    the candidate has built their own, so say so plainly the moment it's
    missing rather than let every task in the session fail silently
    against a broken/absent config with no explanation."""
    if (settings.get_workdir() / "inventory").exists():
        return
    if category in ("ansible_config", "inventory", "managed_nodes"):
        return  # that's precisely what this session is about to practice
    print(fmt.warn(
        f"No inventory found at {settings.get_workdir()}/inventory."))
    print(fmt.dim(
        "  This simulator never writes one for you — building your own "
        "inventory, ansible.cfg, automation user and SSH key from "
        "bootstrap (root/password) access is task 1, exactly like the "
        "real exam. Every other task in this session will fail its "
        "execution/state checks without one.\n"
        "  python3 rhce_simulator.py --learn            (Configuring managed nodes)\n"
        "  python3 rhce_simulator.py --practice ansible_config\n"
        "  python3 rhce_simulator.py --practice inventory\n"
        "  python3 rhce_simulator.py --practice managed_nodes\n"))


def cmd_session(mode: str, category: str = None):
    from core.engine import Session
    from core.registry import TaskRegistry
    if category and category not in TaskRegistry.get_all_categories():
        cats = ", ".join(TaskRegistry.get_all_categories())
        print(fmt.fail(f"Unknown category '{category}'. Available: {cats}"))
        return 1
    warn_if_no_inventory(category)
    Session(mode, category=category).run()
    return 0


def cmd_focus(weak_count: int = 4):
    """A practice session drawn from the candidate's own weakest
    categories — never-attempted categories count as weakest of all."""
    from core.engine import Session
    from core.registry import TaskRegistry
    from core.results_db import ResultsDB
    db = ResultsDB()
    all_cats = TaskRegistry.get_all_categories()
    weakest = db.weak_categories(all_cats)[:weak_count]
    db.close()
    warn_if_no_inventory()
    print(fmt.banner("Focus session — your weakest categories"))
    for cat in weakest:
        print(f"  {settings.CATEGORY_DISPLAY.get(cat, cat)}")
    print()
    Session("focus", categories=weakest).run()
    return 0


def cmd_reset_progress():
    from core.results_db import ResultsDB
    reply = input("This permanently clears all tracked session history and "
                  "category stats. Continue? [y/N] ").strip().lower()
    if reply not in ("y", "yes"):
        print(fmt.dim("Cancelled — nothing was reset."))
        return 0
    db = ResultsDB()
    db.reset()
    db.close()
    print(fmt.ok("Progress history cleared."))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=f"{settings.EXAM_NAME} exam simulator v{settings.VERSION}")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--quick", action="store_true", help="5 random tasks")
    group.add_argument("--exam", action="store_true",
                       help=f"full exam ({settings.EXAM_TASK_COUNT} tasks)")
    group.add_argument("--practice", metavar="CATEGORY",
                       help="drill a single category")
    group.add_argument("--focus", action="store_true",
                       help="practice session weighted to your weakest categories")
    group.add_argument("--list-tasks", action="store_true",
                       help="show the task catalog")
    group.add_argument("--learn", action="store_true",
                       help="show EX294 objectives")
    group.add_argument("--history", action="store_true",
                       help="show past session results")
    group.add_argument("--reset-progress", action="store_true",
                       help="clear tracked session history (asks to confirm)")
    args = parser.parse_args(argv)

    if args.list_tasks:
        cmd_list_tasks()
    elif args.learn:
        cmd_learn()
    elif args.history:
        cmd_history()
    elif args.reset_progress:
        return cmd_reset_progress()
    elif args.quick:
        return cmd_session("quick")
    elif args.exam:
        return cmd_session("exam")
    elif args.practice:
        return cmd_session("practice", category=args.practice)
    elif args.focus:
        return cmd_focus()
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
