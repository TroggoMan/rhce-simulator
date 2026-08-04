"""
SQLite progress tracking — slimmed-down port of rhcsa-simulator's ResultsDB.
One row per session, one per task result; enough for history and a
per-category weakness report.
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    started TEXT NOT NULL,
    finished TEXT,
    score INTEGER DEFAULT 0,
    max_score INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS task_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    task_id TEXT NOT NULL,
    category TEXT NOT NULL,
    passed INTEGER NOT NULL,
    score INTEGER NOT NULL,
    max_score INTEGER NOT NULL
);
-- SM-2 spaced-repetition state, one row per category. Scheduled per
-- category rather than per task on purpose: tasks randomise their
-- parameters, so the same task id is never repeated identically, and
-- per-task scheduling would track something the candidate never sees twice.
CREATE TABLE IF NOT EXISTS category_srs (
    category TEXT PRIMARY KEY,
    easiness_factor REAL DEFAULT 2.5,
    interval_days INTEGER DEFAULT 1,
    repetitions INTEGER DEFAULT 0,
    due TEXT,
    last_attempt TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ResultsDB:
    def __init__(self, path: Path = None):
        self.path = Path(path or settings.RESULTS_DB)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(SCHEMA)

    def start_session(self, mode: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO sessions (mode, started) VALUES (?, ?)", (mode, _now()))
        self.conn.commit()
        return cur.lastrowid

    def record_task(self, session_id: int, task, result):
        self.conn.execute(
            "INSERT INTO task_results (session_id, task_id, category, passed,"
            " score, max_score) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, task.id, task.category, int(result.passed),
             result.score, result.max_score))
        self._update_srs(task.category, result.score, result.max_score,
                         result.passed)
        self.conn.commit()

    # -- spaced repetition -------------------------------------------------

    def _update_srs(self, category: str, score: int, max_score: int,
                    passed: bool):
        """Advance this category's SM-2 schedule after an attempt.

        Quality mapping note, inherited from the sibling project and worth
        keeping: a perfect score has to map to 5. At q=4 the easiness-factor
        delta is exactly zero, so if the best attainable grade were 4 the EF
        could only hold flat or decay toward its 1.3 floor, and intervals
        would never grow — a category you keep acing would keep coming back
        forever.
        """
        row = self.conn.execute(
            "SELECT easiness_factor, interval_days, repetitions"
            " FROM category_srs WHERE category = ?", (category,)).fetchone()
        ef, interval, reps = row if row else (2.5, 1, 0)

        if passed:
            if score >= max_score:
                quality = 5
            elif score >= max_score * 0.9:
                quality = 4
            else:
                quality = 3
            reps += 1
            interval = 1 if reps == 1 else (6 if reps == 2 else int(interval * ef))
        else:
            quality = 1
            reps = 0
            interval = 1

        ef = max(1.3, ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        now = datetime.now(timezone.utc)
        due = (now + timedelta(days=max(1, interval))).isoformat(timespec="seconds")
        self.conn.execute(
            "INSERT INTO category_srs (category, easiness_factor, interval_days,"
            " repetitions, due, last_attempt) VALUES (?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(category) DO UPDATE SET"
            " easiness_factor=excluded.easiness_factor,"
            " interval_days=excluded.interval_days,"
            " repetitions=excluded.repetitions,"
            " due=excluded.due, last_attempt=excluded.last_attempt",
            (category, ef, interval, reps, due,
             now.isoformat(timespec="seconds")))

    def due_categories(self, all_categories) -> list:
        """Categories to drill now, most overdue first.

        Never-attempted categories come first — nothing is more overdue than
        something never seen. Then anything past its due date, oldest first.
        Categories not yet due are omitted entirely: that is the whole point
        of spaced repetition, and including them would just reproduce
        weak_categories().
        """
        rows = {cat: due for cat, due in self.conn.execute(
            "SELECT category, due FROM category_srs").fetchall()}
        now = _now()
        unseen = [c for c in all_categories if c not in rows or not rows[c]]
        overdue = sorted((c for c in all_categories
                          if c in rows and rows[c] and rows[c] <= now),
                         key=lambda c: rows[c])
        return unseen + overdue

    def srs_stats(self):
        """(category, repetitions, interval_days, easiness_factor, due)."""
        return self.conn.execute(
            "SELECT category, repetitions, interval_days, easiness_factor, due"
            " FROM category_srs ORDER BY due").fetchall()

    def finish_session(self, session_id: int, score: int, max_score: int):
        self.conn.execute(
            "UPDATE sessions SET finished=?, score=?, max_score=? WHERE id=?",
            (_now(), score, max_score, session_id))
        self.conn.commit()

    def history(self, limit: int = 15):
        return self.conn.execute(
            "SELECT id, mode, started, score, max_score FROM sessions"
            " WHERE finished IS NOT NULL ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()

    def category_stats(self):
        """(category, attempts, passes) across all sessions."""
        return self.conn.execute(
            "SELECT category, COUNT(*), SUM(passed) FROM task_results"
            " GROUP BY category ORDER BY category").fetchall()

    def weak_categories(self, all_categories) -> list:
        """Every known category, worst-first: never-attempted categories
        sort first (an untested category is the weakest possible signal),
        then attempted categories ascending by pass rate."""
        stats = {cat: (attempts, passes or 0)
                for cat, attempts, passes in self.category_stats()}
        def rank(cat):
            if cat not in stats:
                return (0, 0.0)
            attempts, passes = stats[cat]
            return (1, passes / attempts if attempts else 0.0)
        return sorted(all_categories, key=rank)

    def reset(self):
        """Wipe all tracked history — a fresh start for a candidate who
        wants their pass-rate/weak-area stats to stop reflecting old
        practice (e.g. after a long break, or before a final study push)."""
        self.conn.executescript(
            "DELETE FROM task_results; DELETE FROM sessions;"
            " DELETE FROM category_srs;")
        self.conn.commit()

    def close(self):
        self.conn.close()
