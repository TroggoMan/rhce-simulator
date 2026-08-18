"""
--browser: one persistent HTTP server for the whole simulator, not just a
session's task sheet.

WHY
---
core/task_gui.py already lets a running session be driven entirely from a
browser (submit for grading, dispute, reset the lab). What it doesn't cover
is everything *before* a session exists: picking a mode, browsing Learn
content, and reviewing History all still required the terminal. This module
adds a "lobby" view in front of that same panel, on the same port, so
starting a session is a click instead of a new command line — the browser
never has to navigate anywhere else.

The lobby's Setup tab surfaces the same live lab-connection facts --setup
prints in the terminal (_setup_snapshot, sharing settings.lab_connection_rows)
— but not the rest of --setup: no inventory-vs-lab diffing, no live
ansible -m ping. Those stay CLI-only, same as --reset-progress
(destructive; a real terminal confirmation prompt is the right amount of
friction for wiping tracked history).

SHAPE
-----
LobbyController is the panel's controller for its whole life. While no
session is running it answers lobby actions (start_session, quit_session)
directly; once a session starts, it transparently forwards session actions
(request_validate, file_dispute, reset_lab, list_disputes) to that
session's own PanelController — so core/task_gui.py's action dispatch needs
no lobby-awareness at all, it just calls whatever it already calls.

The session itself runs on a background thread via Session.run() with
gui=False (so it never tries to open a second, competing HTTP server) but
with its own PanelController wired up manually, so panel-driven submit/
dispute/reset still work exactly as they do for a terminal-launched
session. Quitting from the browser (no terminal 'q' available here) uses
PanelController.request_quit(), added alongside this module.
"""

import logging
import threading

from config import settings
from config.learn_content import CONTENT
from core import task_gui
from core.panel_control import PanelController
from core.registry import TaskRegistry

logger = logging.getLogger(__name__)

_VALID_MODES = ("quick", "exam", "practice", "focus", "adaptive")

# Actions that only mean something once a session exists — forwarded to
# that session's own PanelController rather than implemented here.
_SESSION_ACTIONS = ("request_validate", "file_dispute", "reset_lab",
                    "list_disputes")


def _learn_tree():
    """Domain -> categories -> authored content, for the Learn view.

    Mirrors core/learn.py's browse order. A category with no authored
    content yet still appears (content: null) rather than being hidden —
    same "never silently omit a gap" rule learn.py follows.
    """
    domains = []
    for domain, title in settings.EXAM_DOMAINS.items():
        cats = sorted(cat for cat, d in settings.CATEGORY_TO_DOMAIN.items()
                      if d == domain)
        domains.append({
            "domain": domain,
            "title": title,
            "categories": [{
                "id": cat,
                "label": settings.CATEGORY_DISPLAY.get(cat, cat),
                "count": TaskRegistry.get_task_count(cat),
                "content": CONTENT.get(cat),
            } for cat in cats],
        })
    return domains


def _category_list():
    return [{"id": cat, "label": settings.CATEGORY_DISPLAY.get(cat, cat),
             "count": TaskRegistry.get_task_count(cat)}
            for cat in TaskRegistry.get_all_categories()]


def _setup_snapshot():
    """Live lab connection facts for the lobby's Setup tab — the same
    read-only lookup --setup uses in the terminal (settings.lab_connection_rows),
    reshaped for the browser: which nodes are up, their host/port, and a
    ready-to-copy example inventory. Deliberately NOT the full --setup
    diagnostic (no inventory-vs-lab diffing, no live ansible -m ping) —
    just the facts a candidate needs to actually write the file, cheap and
    side-effect-free enough to compute on every /api/state poll."""
    import os

    lab_type, nodes = settings.detect_lab_type_and_nodes()
    if not lab_type:
        return {"lab_type": None, "nodes": [], "example_inventory": None}

    rows = settings.lab_connection_rows(lab_type, nodes)
    node_list = [{"name": n, "host": h, "port": p} for n, h, _dp, p in rows]
    example = "\n".join(
        f"{n} ansible_host={h}" + ("" if p == 22 else f" ansible_port={p}")
        for n, h, _dp, p in rows)
    return {
        "lab_type": lab_type,
        "nodes": node_list,
        "example_inventory": example or None,
        "root_password": os.environ.get("RHCE_LAB_ROOT_PASSWORD", "rhce-lab"),
    }


def _history_snapshot():
    from core.results_db import ResultsDB
    db = ResultsDB()
    try:
        sessions = [{
            "id": sid, "mode": mode, "started": started,
            "score": score, "max_score": max_score,
            "percentage": round(100 * score / max_score) if max_score else 0,
        } for sid, mode, started, score, max_score in db.history()]
        stats = [{
            "category": cat, "label": settings.CATEGORY_DISPLAY.get(cat, cat),
            "attempts": attempts, "passes": passes or 0,
        } for cat, attempts, passes in db.category_stats()]
        return {"sessions": sessions, "stats": stats}
    finally:
        db.close()


class LobbyController:
    """The panel's controller for the whole --browser process lifetime."""

    def __init__(self):
        self.session = None
        self._thread = None
        self._lock = threading.Lock()

    # -- state for GET /api/state, when no session is running -----------

    def lobby_state(self):
        if self.session is not None:
            return None
        return {
            "view": "lobby",
            "exam_name": settings.EXAM_NAME,
            "categories": _category_list(),
            "learn": _learn_tree(),
            "history": _history_snapshot(),
            "setup": _setup_snapshot(),
        }

    # -- lifecycle ---------------------------------------------------------

    def start_session(self, mode=None, category=None):
        with self._lock:
            if self.session is not None:
                return {"ok": False, "error": "A session is already running."}
            if mode not in _VALID_MODES:
                return {"ok": False, "error": f"Unknown mode {mode!r}."}
            all_cats = TaskRegistry.get_all_categories()
            if category and category not in all_cats:
                return {"ok": False, "error": f"Unknown category {category!r}."}

            from core.results_db import ResultsDB

            # Plain category-name lists are fine to hand across threads;
            # only the ResultsDB *connection* itself is thread-affine — see
            # the note on Session construction below.
            categories = None
            if mode in ("focus", "adaptive"):
                db = ResultsDB()
                try:
                    categories = (db.due_categories(all_cats) if mode == "adaptive"
                                 else db.weak_categories(all_cats))[:4]
                finally:
                    db.close()
                if mode == "adaptive" and not categories:
                    return {"ok": False,
                            "error": "Nothing is due for review right now "
                                    "— try Focus or Practice instead."}

            practice_category = category if mode == "practice" else None

            def _run():
                # Session() opens its own ResultsDB connection and holds it
                # for the session's whole life (used again in finish());
                # sqlite3 connections are thread-affine, so both the
                # construction and every later use must happen on this
                # same background thread — never on the HTTP worker thread
                # that handled the /api/start request.
                from core.engine import Session
                session = Session(mode, category=practice_category,
                                  categories=categories, gui=False,
                                  headless=True)
                session.controller = PanelController(session)
                self.session = session
                try:
                    session.run()
                finally:
                    with self._lock:
                        self.session = None

            self._thread = threading.Thread(target=_run, daemon=True,
                                            name="rhce-browser-session")
            self._thread.start()
            return {"ok": True}

    def quit_session(self):
        session = self.session
        if session is None or session.controller is None:
            return {"ok": False, "error": "No session running."}
        return session.controller.request_quit()

    # -- delegate to the live session's own controller -------------------

    def __getattr__(self, name):
        if name not in _SESSION_ACTIONS:
            raise AttributeError(name)

        def _call(*args, **kwargs):
            session = self.session
            if session is None or session.controller is None:
                return {"ok": False, "error": "No session running."}
            return getattr(session.controller, name)(*args, **kwargs)
        return _call


def start(port=None, bind="0.0.0.0"):
    """Start the persistent lobby+session panel. Never raises."""
    lobby = LobbyController()

    def provider():
        state = lobby.lobby_state()
        if state is not None:
            return state
        session = lobby.session
        remaining = None
        clock = getattr(session, "clock", None)
        if clock is not None:
            remaining = max(0, int(clock.remaining))
        state = task_gui.build_state(getattr(session, "tasks", []), remaining)
        state["view"] = "session"
        state["mode"] = getattr(session, "mode", "")
        state["status"] = getattr(session, "panel_status", "in_progress")
        state["results"] = getattr(session, "panel_results", None)
        state["can_control"] = True
        # Nothing is driving the terminal loop for a --browser session —
        # the panel shows a Quit button since 'q' isn't an option here.
        state["headless"] = True
        return state

    panel = task_gui.TaskPanel(provider, controller=lobby,
                               port=port or task_gui.DEFAULT_PORT, bind=bind)
    urls = panel.start()
    return (panel, urls) if urls else (None, [])
