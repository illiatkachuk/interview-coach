"""Історія задач і спроб у SQLite."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS problems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    title TEXT NOT NULL,
    statement TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id INTEGER NOT NULL REFERENCES problems(id),
    solution_path TEXT NOT NULL,
    solution_code TEXT NOT NULL,
    run_stdout TEXT NOT NULL,
    run_stderr TEXT NOT NULL,
    exit_code INTEGER NOT NULL,
    timed_out INTEGER NOT NULL DEFAULT 0,
    verdict TEXT,
    score INTEGER,
    feedback TEXT,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    """Тонка обгортка над sqlite3 для problems/attempts."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- problems ---

    def add_problem(self, topic: str, difficulty: str, title: str, statement: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO problems (topic, difficulty, title, statement, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (topic, difficulty, title, statement, _now()),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_problem(self, problem_id: int) -> sqlite3.Row | None:
        cur = self._conn.execute("SELECT * FROM problems WHERE id = ?", (problem_id,))
        return cur.fetchone()

    def list_problems(self) -> list[sqlite3.Row]:
        cur = self._conn.execute("SELECT * FROM problems ORDER BY id")
        return cur.fetchall()

    # --- attempts ---

    def add_attempt(
        self,
        problem_id: int,
        solution_path: str,
        solution_code: str,
        run_stdout: str,
        run_stderr: str,
        exit_code: int,
        timed_out: bool,
        verdict: str | None,
        score: int | None,
        feedback: str | None,
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO attempts (problem_id, solution_path, solution_code, run_stdout,"
            " run_stderr, exit_code, timed_out, verdict, score, feedback, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                problem_id,
                solution_path,
                solution_code,
                run_stdout,
                run_stderr,
                exit_code,
                int(timed_out),
                verdict,
                score,
                feedback,
                _now(),
            ),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_attempts(self, problem_id: int | None = None) -> list[sqlite3.Row]:
        if problem_id is None:
            cur = self._conn.execute(
                "SELECT a.*, p.title AS problem_title, p.topic AS problem_topic"
                " FROM attempts a JOIN problems p ON p.id = a.problem_id ORDER BY a.id"
            )
        else:
            cur = self._conn.execute(
                "SELECT a.*, p.title AS problem_title, p.topic AS problem_topic"
                " FROM attempts a JOIN problems p ON p.id = a.problem_id"
                " WHERE a.problem_id = ? ORDER BY a.id",
                (problem_id,),
            )
        return cur.fetchall()
