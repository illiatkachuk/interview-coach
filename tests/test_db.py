"""Tests for the storage layer (SQLite)."""

from interview_coach.db import Database


def test_add_and_get_problem(db):
    pid = db.add_problem("dynamic-programming", "medium", "Coin Change", "Find...")
    problem = db.get_problem(pid)
    assert problem["id"] == pid
    assert problem["topic"] == "dynamic-programming"
    assert problem["difficulty"] == "medium"
    assert problem["title"] == "Coin Change"
    assert problem["statement"] == "Find..."
    assert problem["created_at"]


def test_get_missing_problem_returns_none(db):
    assert db.get_problem(999) is None


def test_list_problems_ordered(db):
    first = db.add_problem("graphs", "easy", "BFS", "...")
    second = db.add_problem("dp", "hard", "LIS", "...")
    problems = db.list_problems()
    assert [p["id"] for p in problems] == [first, second]


def test_add_and_list_attempts(db):
    pid = db.add_problem("dp", "medium", "Coin Change", "...")
    aid = db.add_attempt(
        pid,
        "sol.py",
        "print(1)",
        "1\n",
        "",
        0,
        False,
        verdict="correct",
        score=9,
        feedback="Good solution",
    )
    attempts = db.list_attempts()
    assert len(attempts) == 1
    attempt = attempts[0]
    assert attempt["id"] == aid
    assert attempt["problem_id"] == pid
    assert attempt["problem_title"] == "Coin Change"
    assert attempt["verdict"] == "correct"
    assert attempt["score"] == 9
    assert attempt["timed_out"] == 0


def test_list_attempts_filtered_by_problem(db):
    p1 = db.add_problem("dp", "easy", "A", "...")
    p2 = db.add_problem("dp", "easy", "B", "...")
    db.add_attempt(p1, "a.py", "", "", "", 0, False, None, None, None)
    db.add_attempt(p2, "b.py", "", "", "", 1, False, None, None, None)
    assert len(db.list_attempts(p1)) == 1
    assert len(db.list_attempts(p2)) == 1
    assert len(db.list_attempts()) == 2


def test_attempt_without_feedback_allowed(db):
    pid = db.add_problem("dp", "easy", "A", "...")
    db.add_attempt(pid, "a.py", "code", "", "boom", 1, False, None, None, None)
    attempt = db.list_attempts(pid)[0]
    assert attempt["verdict"] is None
    assert attempt["score"] is None
    assert attempt["feedback"] is None


def test_db_creates_parent_directory(tmp_path):
    nested = tmp_path / "deep" / "nested" / "history.db"
    with Database(nested) as database:
        database.add_problem("dp", "easy", "A", "...")
    assert nested.exists()
