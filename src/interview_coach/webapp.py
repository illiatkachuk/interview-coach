"""FastAPI web application: a REST API over the core modules plus a static frontend.

The endpoints reuse llm.py / db.py / runner.py directly — the same code paths
the CLI uses, against the same SQLite database.
"""

import tempfile
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, llm
from .config import DEFAULT_LANG, RUN_TIMEOUT_SECONDS, db_path, load_dotenv
from .db import Database
from .runner import run_solution

STATIC_DIR = Path(__file__).parent / "static"


class ProblemRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    lang: str = Field(default=DEFAULT_LANG, max_length=10)


class AttemptRequest(BaseModel):
    code: str = Field(min_length=1, max_length=200_000)
    lang: str = Field(default=DEFAULT_LANG, max_length=10)
    timeout: int = Field(default=RUN_TIMEOUT_SECONDS, ge=1, le=120)


def _problem_summary(row) -> dict:
    return {
        "id": row["id"],
        "topic": row["topic"],
        "difficulty": row["difficulty"],
        "title": row["title"],
        "created_at": row["created_at"],
    }


def _problem_full(row) -> dict:
    return {**_problem_summary(row), "statement": row["statement"]}


def _attempt_dict(row) -> dict:
    return {
        "id": row["id"],
        "problem_id": row["problem_id"],
        "problem_title": row["problem_title"],
        "problem_topic": row["problem_topic"],
        "verdict": row["verdict"],
        "score": row["score"],
        "feedback": row["feedback"],
        "solution_code": row["solution_code"],
        "stdout": row["run_stdout"],
        "stderr": row["run_stderr"],
        "exit_code": row["exit_code"],
        "timed_out": bool(row["timed_out"]),
        "created_at": row["created_at"],
    }


def create_app() -> FastAPI:
    load_dotenv()
    app = FastAPI(title="interview-coach", version=__version__)

    def open_db() -> Database:
        # A fresh connection per request: sqlite3 objects must stay on one
        # thread, and endpoints run in a threadpool.
        return Database(db_path())

    @app.post("/api/problems", status_code=201)
    def create_problem(req: ProblemRequest) -> dict:
        topic = req.topic.strip()
        if not topic:
            raise HTTPException(status_code=422, detail="Topic must not be blank.")
        try:
            problem = llm.generate_problem(topic, difficulty=req.difficulty, lang=req.lang)
        except llm.LLMError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        with open_db() as db:
            problem_id = db.add_problem(
                topic, req.difficulty, problem["title"], problem["statement"]
            )
            row = db.get_problem(problem_id)
        return _problem_full(row)

    @app.get("/api/problems")
    def list_problems() -> list[dict]:
        with open_db() as db:
            return [_problem_summary(row) for row in db.list_problems()]

    @app.get("/api/problems/{problem_id}")
    def get_problem(problem_id: int) -> dict:
        with open_db() as db:
            row = db.get_problem(problem_id)
        if row is None:
            raise HTTPException(
                status_code=404, detail=f"Problem #{problem_id} does not exist."
            )
        return _problem_full(row)

    @app.post("/api/problems/{problem_id}/attempts", status_code=201)
    def create_attempt(problem_id: int, req: AttemptRequest) -> dict:
        with open_db() as db:
            problem = db.get_problem(problem_id)
            if problem is None:
                raise HTTPException(
                    status_code=404, detail=f"Problem #{problem_id} does not exist."
                )

            with tempfile.TemporaryDirectory(prefix="interview-coach-") as tmp:
                solution_path = Path(tmp) / "solution.py"
                solution_path.write_text(req.code, encoding="utf-8")
                result = run_solution(solution_path, timeout=req.timeout)

            verdict = score = feedback = llm_error = None
            try:
                fb = llm.review_solution(
                    problem_statement=problem["statement"],
                    solution_code=req.code,
                    run_stdout=result.stdout,
                    run_stderr=result.stderr,
                    exit_code=result.exit_code,
                    timed_out=result.timed_out,
                    lang=req.lang,
                )
                verdict, score, feedback = fb.verdict, fb.score, fb.feedback
            except llm.LLMError as exc:
                # Save the attempt anyway — without feedback (same as the CLI).
                llm_error = str(exc)

            attempt_id = db.add_attempt(
                problem_id,
                "web",
                req.code,
                result.stdout,
                result.stderr,
                result.exit_code,
                result.timed_out,
                verdict=verdict,
                score=score,
                feedback=feedback,
            )

        return {
            "id": attempt_id,
            "problem_id": problem_id,
            "verdict": verdict,
            "score": score,
            "feedback": feedback,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "llm_error": llm_error,
        }

    @app.get("/api/attempts")
    def list_attempts(problem_id: int | None = None) -> list[dict]:
        with open_db() as db:
            return [_attempt_dict(row) for row in db.list_attempts(problem_id)]

    # Mounted last so /api/* routes take priority; html=True serves index.html at /.
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
