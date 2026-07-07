#!/usr/bin/env python3
"""
RHCE EX294 (RHEL 10) Exam Simulator — main entry point.

Sibling project to rhcsa-simulator. Presents exam-style Ansible automation
tasks, then grades them by running the candidate's own playbooks against
their own inventory and checking the resulting state on managed nodes.

Usage:
    python3 rhce_simulator.py --quick             # 5 random tasks
    python3 rhce_simulator.py --exam              # full exam (15 tasks)
    python3 rhce_simulator.py --practice roles    # drill one category
    python3 rhce_simulator.py --list-tasks        # catalog overview
    python3 rhce_simulator.py --learn             # EX294 objectives
    python3 rhce_simulator.py --history           # past sessions

Environment:
    RHCE_SIM_WORKDIR      Ansible working dir (default ~/ansible)
    RHCE_SIM_NODES        comma-separated managed nodes (default localhost)
    RHCE_SIM_REMOTE_USER  remote user for task wording (default devops)
"""

import argparse
import sys

from config import settings, exam_objectives
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


def cmd_learn():
    print(fmt.banner(f"{settings.EXAM_NAME} — exam objectives"))
    for domain, title in settings.EXAM_DOMAINS.items():
        print(f"\n{C.BOLD}Domain {domain}: {title}{C.RESET}")
        for point in exam_objectives.OBJECTIVES.get(domain, []):
            print(f"   • {point}")
    print(f"\n{fmt.warn(exam_objectives.FOUNDATION_NOTE)}")


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


def cmd_session(mode: str, category: str = None):
    from core.engine import Session
    from core.registry import TaskRegistry
    if category and category not in TaskRegistry.get_all_categories():
        cats = ", ".join(TaskRegistry.get_all_categories())
        print(fmt.fail(f"Unknown category '{category}'. Available: {cats}"))
        return 1
    Session(mode, category=category).run()
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
    group.add_argument("--list-tasks", action="store_true",
                       help="show the task catalog")
    group.add_argument("--learn", action="store_true",
                       help="show EX294 objectives")
    group.add_argument("--history", action="store_true",
                       help="show past session results")
    args = parser.parse_args(argv)

    if args.list_tasks:
        cmd_list_tasks()
    elif args.learn:
        cmd_learn()
    elif args.history:
        cmd_history()
    elif args.quick:
        return cmd_session("quick")
    elif args.exam:
        return cmd_session("exam")
    elif args.practice:
        return cmd_session("practice", category=args.practice)
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
