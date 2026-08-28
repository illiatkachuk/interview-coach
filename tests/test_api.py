"""REST API tests (FastAPI TestClient, LLM mocked)."""

import pytest
from fastapi.testclient import TestClient

from interview_coach import webapp
from interview_coach.llm import Feedback, LLMError


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("INTERVIEW_COACH_DB", str(tmp_path / "history.db"))
    with TestClient(webapp.app) as test_client:
        yield test_client


@pytest.fixture
def fake_problem(monkeypatch):
    def _generate(topic, difficulty="medium", lang="en", client=None):
        return {
            "title": f"Problem about {topic}",
            "statement": f"# Statement ({difficulty})\nDo something with {topic}.",
        }

    monkeypatch.setattr(webapp.llm, "generate_problem", _generate)


@pytest.fixture
def fake_review(monkeypatch):
    def _review(**kwargs):
        return Feedback(verdict="correct", score=8, feedback="Good, but could be better.")

    monkeypatch.setattr(webapp.llm, "review_solution", _review)


def test_create_problem(client, fake_problem):
    resp = client.post("/api/problems", json={"topic": "graphs", "difficulty": "easy"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == 1
    assert data["topic"] == "graphs"
    assert data["difficulty"] == "easy"
    assert data["title"] == "Problem about graphs"
    assert "Statement" in data["statement"]
    assert data["created_at"]


def test_create_problem_validation(client, fake_problem):
    assert client.post("/api/problems", json={}).status_code == 422
    assert client.post("/api/problems", json={"topic": "   "}).status_code == 422
    assert (
        client.post(
            "/api/problems", json={"topic": "x", "difficulty": "impossible"}
        ).status_code
        == 422
    )


def test_create_problem_llm_error(client, monkeypatch):
    def _boom(*args, **kwargs):
        raise LLMError("no key")

    monkeypatch.setattr(webapp.llm, "generate_problem", _boom)
    resp = client.post("/api/problems", json={"topic": "dp"})
    assert resp.status_code == 502
    assert "no key" in resp.json()["detail"]


def test_list_problems(client, fake_problem):
    assert client.get("/api/problems").json() == []
    client.post("/api/problems", json={"topic": "dp"})
    problems = client.get("/api/problems").json()
    assert len(problems) == 1
    assert problems[0]["title"] == "Problem about dp"
    assert "statement" not in problems[0]


def test_get_problem_and_404(client, fake_problem):
    client.post("/api/problems", json={"topic": "dp"})
    assert "Statement" in client.get("/api/problems/1").json()["statement"]
    resp = client.get("/api/problems/42")
    assert resp.status_code == 404
    assert "does not exist" in resp.json()["detail"]


def test_submit_attempt_full_flow(client, fake_problem, fake_review):
    client.post("/api/problems", json={"topic": "dp"})
    resp = client.post("/api/problems/1/attempts", json={"code": "print('42')"})
    assert resp.status_code == 201
    attempt = resp.json()
    assert attempt["verdict"] == "correct"
    assert attempt["score"] == 8
    assert "42" in attempt["stdout"]
    assert attempt["exit_code"] == 0
    assert attempt["llm_error"] is None

    attempts = client.get("/api/attempts").json()
    assert len(attempts) == 1
    assert attempts[0]["problem_title"] == "Problem about dp"
    assert attempts[0]["solution_code"] == "print('42')"


def test_submit_attempt_missing_problem(client):
    resp = client.post("/api/problems/99/attempts", json={"code": "print(1)"})
    assert resp.status_code == 404


def test_submit_attempt_validation(client, fake_problem):
    client.post("/api/problems", json={"topic": "dp"})
    assert client.post("/api/problems/1/attempts", json={"code": ""}).status_code == 422
    assert (
        client.post(
            "/api/problems/1/attempts", json={"code": "x", "timeout": 0}
        ).status_code
        == 422
    )


def test_attempt_saved_even_if_review_fails(client, fake_problem, monkeypatch):
    client.post("/api/problems", json={"topic": "dp"})

    def _boom(**kwargs):
        raise LLMError("API unavailable")

    monkeypatch.setattr(webapp.llm, "review_solution", _boom)
    resp = client.post("/api/problems/1/attempts", json={"code": "print(1)"})
    assert resp.status_code == 201
    attempt = resp.json()
    assert attempt["verdict"] is None
    assert attempt["llm_error"] == "API unavailable"

    saved = client.get("/api/attempts").json()
    assert len(saved) == 1
    assert saved[0]["verdict"] is None


def test_failing_code_still_reviewed(client, fake_problem, fake_review):
    client.post("/api/problems", json={"topic": "dp"})
    resp = client.post(
        "/api/problems/1/attempts", json={"code": "raise RuntimeError('x')"}
    )
    attempt = resp.json()
    assert attempt["exit_code"] != 0
    assert "RuntimeError" in attempt["stderr"]
    assert attempt["verdict"] == "correct"


def test_attempts_filtered_by_problem(client, fake_problem, fake_review):
    client.post("/api/problems", json={"topic": "a"})
    client.post("/api/problems", json={"topic": "b"})
    client.post("/api/problems/1/attempts", json={"code": "print(1)"})
    client.post("/api/problems/2/attempts", json={"code": "print(2)"})
    assert len(client.get("/api/attempts").json()) == 2
    only = client.get("/api/attempts", params={"problem_id": 2}).json()
    assert len(only) == 1
    assert only[0]["problem_id"] == 2


def test_index_page_served(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "Interview Coach" in resp.text
