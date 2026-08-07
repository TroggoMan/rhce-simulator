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


def test_sessions_present_setup_before_the_work_that_needs_it():
    tasks = TaskRegistry.get_random_tasks(settings.EXAM_TASK_COUNT)
    ranks = [settings.sequence_rank(t.category) for t in tasks]
    assert ranks == sorted(ranks), (
        "a session must not ask for a playbook before the inventory it "
        "runs against: " + str([(t.category, r) for t, r in zip(tasks, ranks)]))


def test_adhoc_sorts_after_the_setup_it_depends_on():
    # Domain 2 by objective, but an ad-hoc command needs the inventory and
    # node access from domains 3-4 to run at all.
    assert settings.sequence_rank("adhoc") > settings.sequence_rank("inventory")
    assert settings.sequence_rank("adhoc") > settings.sequence_rank("managed_nodes")
    assert settings.sequence_rank("adhoc") < settings.sequence_rank("playbook_basics")


def test_exam_set_spreads_categories():
    tasks = TaskRegistry.get_random_tasks(settings.EXAM_TASK_COUNT)
    assert len(tasks) == settings.EXAM_TASK_COUNT
    cats = {}
    for t in tasks:
        cats[t.category] = cats.get(t.category, 0) + 1
    assert max(cats.values()) <= 2, f"category overload: {cats}"
