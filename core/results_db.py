"""
SQLite progress tracking — slimmed-down port of rhcsa-simulator's ResultsDB.
One row per session, one per task result; enough for history and a
per-category weakness report.
"""

import sqlite3
from datetime import datetime, timezone
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
        self.conn.commit()

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

    def close(self):
        self.conn.close()
