"""CLI tests via click.testing.CliRunner (LLM mocked)."""

import pytest
from click.testing import CliRunner

from interview_coach import cli as cli_module
from interview_coach import llm
from interview_coach.cli import cli
from interview_coach.llm import Feedback


@pytest.fixture
def runner(tmp_path, monkeypatch):
    monkeypatch.setenv("INTERVIEW_COACH_DB", str(tmp_path / "history.db"))
    return CliRunner()


@pytest.fixture
def fake_problem(monkeypatch):
    def _generate(topic, difficulty="medium", lang="en", client=None):
        return {
            "title": f"Problem about {topic}",
            "statement": f"# Statement ({difficulty})\nDo something with {topic}.",
        }

    monkeypatch.setattr(cli_module.llm, "generate_problem", _generate)


@pytest.fixture
def fake_review(monkeypatch):
    def _review(**kwargs):
        return Feedback(verdict="correct", score=8, feedback="Good, but could be better.")

    monkeypatch.setattr(cli_module.llm, "review_solution", _review)


def test_new_creates_problem(runner, fake_problem):
    result = runner.invoke(cli, ["new", "dynamic-programming"])
    assert result.exit_code == 0, result.output
    assert "Problem #1" in result.output
    assert "dynamic-programming" in result.output
    assert "submit 1" in result.output


def test_new_llm_error_is_clean(runner, monkeypatch):
    def _boom(*args, **kwargs):
        raise llm.LLMError("no key")

    monkeypatch.setattr(cli_module.llm, "generate_problem", _boom)
    result = runner.invoke(cli, ["new", "dp"])
    assert result.exit_code != 0
    assert "no key" in result.output


def test_show_and_history(runner, fake_problem):
    runner.invoke(cli, ["new", "graphs", "-d", "easy"])
    result = runner.invoke(cli, ["show", "1"])
    assert result.exit_code == 0
    assert "Problem about graphs" in result.output

    result = runner.invoke(cli, ["history"])
    assert result.exit_code == 0
    assert "graphs/easy" in result.output


def test_show_missing_problem(runner):
    result = runner.invoke(cli, ["show", "42"])
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_submit_full_flow(runner, fake_problem, fake_review, tmp_path):
    runner.invoke(cli, ["new", "dp"])
    solution = tmp_path / "sol.py"
    solution.write_text("print('42')\n")

    result = runner.invoke(cli, ["submit", "1", str(solution)])
    assert result.exit_code == 0, result.output
    assert "42" in result.output          # solution stdout
    assert "8/10" in result.output        # score
    assert "Good, but could be better." in result.output

    history = runner.invoke(cli, ["history"])
    assert "Attempts:" in history.output
    assert "8/10" in history.output


def test_submit_missing_problem(runner, tmp_path):
    solution = tmp_path / "sol.py"
    solution.write_text("print(1)\n")
    result = runner.invoke(cli, ["submit", "99", str(solution)])
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_submit_saves_attempt_even_if_llm_fails(runner, fake_problem, monkeypatch, tmp_path):
    runner.invoke(cli, ["new", "dp"])

    def _boom(**kwargs):
        raise llm.LLMError("API unavailable")

    monkeypatch.setattr(cli_module.llm, "review_solution", _boom)
    solution = tmp_path / "sol.py"
    solution.write_text("print(1)\n")

    result = runner.invoke(cli, ["submit", "1", str(solution)])
    assert result.exit_code != 0
    assert "saved" in result.output

    history = runner.invoke(cli, ["history"])
    assert "no feedback" in history.output


def test_submit_failing_solution_still_reviewed(runner, fake_problem, fake_review, tmp_path):
    runner.invoke(cli, ["new", "dp"])
    solution = tmp_path / "bad.py"
    solution.write_text("raise RuntimeError('x')\n")
    result = runner.invoke(cli, ["submit", "1", str(solution)])
    assert result.exit_code == 0, result.output
    assert "exited with code" in result.output
    assert "8/10" in result.output


def test_history_empty(runner):
    result = runner.invoke(cli, ["history"])
    assert result.exit_code == 0
    assert "History is empty" in result.output
