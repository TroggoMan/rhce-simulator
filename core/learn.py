"""
Interactive --learn mode: browse exam domains, drill into a category's
real study content (concept explanation, module cheat-sheet with working
syntax, common mistakes, exam tips), then optionally jump straight into
practicing that category. Falls back gracefully to just the raw objective
bullets for any domain/category without authored content yet — never
crashes on a gap in config/learn_content.CONTENT.
"""

from config import settings, exam_objectives
from config.learn_content import CONTENT
from config.settings import C
from core.registry import TaskRegistry
from utils import formatters as fmt


def _categories_for_domain(domain: int):
    return sorted(cat for cat, d in settings.CATEGORY_TO_DOMAIN.items()
                  if d == domain)


def run():
    while True:
        print(fmt.banner(f"{settings.EXAM_NAME} — exam objectives"))
        for domain, title in settings.EXAM_DOMAINS.items():
            cats = _categories_for_domain(domain)
            tag = (f"{len(cats)} categor{'y' if len(cats) == 1 else 'ies'}"
                   if cats else "background reading only")
            print(f"  {domain:2}. {title}  {fmt.dim(f'({tag})')}")
        print(f"\n{fmt.dim(exam_objectives.ABSOLUTE_ZERO_NOTE)}")
        print(f"\n{fmt.dim(exam_objectives.FOUNDATION_NOTE)}")
        print(f"\n{fmt.dim(exam_objectives.PERSISTENCE_NOTE)}")
        print(f"\n{fmt.dim(exam_objectives.UNPUBLISHED_NUMBERS_NOTE)}")
        raw = input(f"\n{C.BOLD}domain number to study, Enter to "
                    f"exit:{C.RESET} ").strip()
        if not raw:
            return
        if not raw.isdigit() or int(raw) not in settings.EXAM_DOMAINS:
            print(fmt.warn(f"pick a domain 1-{max(settings.EXAM_DOMAINS)}"))
            continue
        _show_domain(int(raw))


def _show_domain(domain: int):
    while True:
        print(fmt.banner(f"Domain {domain}: {settings.EXAM_DOMAINS[domain]}"))
        for point in exam_objectives.OBJECTIVES.get(domain, []):
            print(f"   • {point}")
        cats = _categories_for_domain(domain)
        if not cats:
            print(fmt.dim("\nNo dedicated practice category for this domain "
                          "in the simulator — see the bullets above, and "
                          "the sibling rhcsa-simulator project for Domain 1."))
            input(f"\n{fmt.dim('Enter to go back...')}")
            return
        print()
        for i, cat in enumerate(cats, 1):
            count = TaskRegistry.get_task_count(cat)
            print(f"  {i}. {settings.CATEGORY_DISPLAY.get(cat, cat)} "
                  f"{fmt.dim(f'({count} tasks)')}")
        raw = input(f"\n{C.BOLD}topic number, Enter to go back:{C.RESET} ").strip()
        if not raw:
            return
        if not raw.isdigit() or not 1 <= int(raw) <= len(cats):
            print(fmt.warn(f"pick 1-{len(cats)}"))
            continue
        _show_topic(cats[int(raw) - 1])


def _show_topic(category: str):
    topic = CONTENT.get(category)
    print(fmt.banner(settings.CATEGORY_DISPLAY.get(category, category)))
    if not topic:
        print(fmt.dim("No authored study content yet for this category — "
                      "see the domain's objective bullets for now."))
        input(f"\n{fmt.dim('Enter to go back...')}")
        return

    print(f"{C.BOLD}Concept:{C.RESET}")
    print(topic["explanation"].strip())

    print(f"\n{C.BOLD}Modules & syntax:{C.RESET}")
    for cmd in topic["commands"]:
        print(f"\n  {C.CYAN}{cmd['name']}{C.RESET}")
        for line in cmd["syntax"].splitlines():
            print(f"    {line}")
        if cmd.get("example") and cmd["example"] != cmd["syntax"]:
            print(f"    {fmt.dim('e.g.')}")
            for line in cmd["example"].splitlines():
                print(f"      {line}")
        if cmd.get("notes"):
            print(f"    {fmt.dim(cmd['notes'])}")

    print(f"\n{C.BOLD}Common mistakes:{C.RESET}")
    for m in topic["common_mistakes"]:
        print(f"  {fmt.fail(m)}")

    print(f"\n{C.BOLD}Exam tips:{C.RESET}")
    for t in topic["exam_tips"]:
        print(f"  {C.YELLOW}!{C.RESET} {t}")

    choice = input(f"\n{C.BOLD}[P] practice this category  "
                   f"[Enter] back:{C.RESET} ").strip().lower()
    if choice == "p":
        from core.engine import Session
        Session("practice", category=category).run()
