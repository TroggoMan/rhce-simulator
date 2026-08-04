"""
Task registry with auto-discovery, same pattern as rhcsa-simulator:
task classes register themselves with a decorator; importing the tasks
package via discover() pulls every module in so registration runs.
"""

import importlib
import logging
import pkgutil
import random
from collections import defaultdict

from config import settings

logger = logging.getLogger(__name__)


class TaskRegistry:
    """Central registry for all task classes."""

    _tasks = defaultdict(list)
    _discovered = False

    @classmethod
    def register(cls, category):
        def wrapper(task_class):
            cls._tasks[category].append(task_class)
            logger.debug("Registered %s in %s", task_class.__name__, category)
            return task_class
        return wrapper

    @classmethod
    def discover(cls):
        """Import every module under tasks/ so decorators run."""
        if cls._discovered:
            return
        import tasks as tasks_pkg
        for mod in pkgutil.iter_modules(tasks_pkg.__path__):
            if mod.name not in ("base",):
                importlib.import_module(f"tasks.{mod.name}")
        cls._discovered = True

    # -- queries ---------------------------------------------------------

    @classmethod
    def get_all_categories(cls):
        cls.discover()
        return sorted(cls._tasks.keys())

    @classmethod
    def get_tasks_by_category(cls, category):
        cls.discover()
        return list(cls._tasks.get(category, []))

    @classmethod
    def get_task_count(cls, category=None):
        cls.discover()
        if category:
            return len(cls._tasks.get(category, []))
        return sum(len(t) for t in cls._tasks.values())

    @classmethod
    def all_task_classes(cls):
        cls.discover()
        out = []
        for cat in sorted(cls._tasks):
            out.extend(cls._tasks[cat])
        return out

    @classmethod
    def get_random_tasks(cls, count, category=None, categories=None):
        """Instantiate+generate `count` distinct tasks, spread across
        categories when no category filter is given (exam style).

        `category` restricts the pool to one category (--practice).
        `categories` restricts the pool to a specific ORDERED list — used
        by --focus, where the caller wants the pool biased toward the
        weakest categories first (see cmd_focus / Session breadth logic
        below, which still spreads picks across whatever's in the pool)."""
        cls.discover()
        if category:
            pool = list(cls._tasks.get(category, []))
        elif categories:
            pool = [tc for cat in categories for tc in cls._tasks.get(cat, [])]
        else:
            pool = cls.all_task_classes()
        random.shuffle(pool)

        picked, seen_cats = [], defaultdict(int)
        # Prefer breadth: at most 2 per category until the pool forces more.
        for tc in sorted(pool, key=lambda tc: random.random()):
            if len(picked) >= count:
                break
            inst = tc().generate()
            if not category and seen_cats[inst.category] >= 2:
                continue
            seen_cats[inst.category] += 1
            picked.append(inst)
        # Top up if the breadth cap left us short.
        if len(picked) < count:
            for tc in pool:
                if len(picked) >= count:
                    break
                inst = tc().generate()
                if all(p.id != inst.id for p in picked):
                    picked.append(inst)
        return picked
