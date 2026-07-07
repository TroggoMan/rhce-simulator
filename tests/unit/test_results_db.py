from core.results_db import ResultsDB
from core.validator import ValidationResult
from tasks.environment import AnsibleCfgTask


def test_session_roundtrip(tmp_path):
    db = ResultsDB(tmp_path / "results.db")
    sid = db.start_session("quick")

    task = AnsibleCfgTask().generate()
    res = ValidationResult(task_id=task.id, max_score=task.points)
    res.add("a", True)
    db.record_task(sid, task, res)
    db.finish_session(sid, res.score, task.points)

    rows = db.history()
    assert len(rows) == 1
    _, mode, _, score, max_score = rows[0]
    assert mode == "quick" and score == task.points == max_score

    stats = db.category_stats()
    assert stats == [("ansible_config", 1, 1)]
    db.close()


def test_unfinished_sessions_hidden_from_history(tmp_path):
    db = ResultsDB(tmp_path / "results.db")
    db.start_session("exam")  # never finished
    assert db.history() == []
    db.close()
