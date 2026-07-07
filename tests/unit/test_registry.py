from config import settings
from core.registry import TaskRegistry


def test_discovery_finds_a_real_catalog():
    assert TaskRegistry.get_task_count() >= 25


def test_every_category_is_mapped_to_a_domain():
    for cat in TaskRegistry.get_all_categories():
        assert cat in settings.CATEGORY_TO_DOMAIN, f"unmapped category {cat}"
        assert cat in settings.CATEGORY_DISPLAY, f"no display name for {cat}"


def test_task_ids_are_unique():
    ids = [tc().generate().id for tc in TaskRegistry.all_task_classes()]
    assert len(ids) == len(set(ids))


def test_random_tasks_respect_count_and_category():
    tasks = TaskRegistry.get_random_tasks(3, category="playbook_basics")
    assert 1 <= len(tasks) <= 3
    assert all(t.category == "playbook_basics" for t in tasks)


def test_exam_set_spreads_categories():
    tasks = TaskRegistry.get_random_tasks(settings.EXAM_TASK_COUNT)
    assert len(tasks) == settings.EXAM_TASK_COUNT
    cats = {}
    for t in tasks:
        cats[t.category] = cats.get(t.category, 0) + 1
    assert max(cats.values()) <= 2, f"category overload: {cats}"
