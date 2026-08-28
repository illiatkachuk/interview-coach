"""Tests for the LLM layer with a mocked Anthropic client."""

import pytest

from interview_coach import llm
from conftest import fake_client


def test_generate_problem_parses_response():
    client = fake_client([{"title": "Coin Change", "statement": "# Statement\n..."}])
    problem = llm.generate_problem("dynamic-programming", client=client)
    assert problem == {"title": "Coin Change", "statement": "# Statement\n..."}


def test_generate_problem_request_shape():
    client = fake_client([{"title": "T", "statement": "S"}])
    llm.generate_problem("graphs", difficulty="hard", lang="en", client=client)
    call = client.messages.calls[0]
    assert call["model"] == llm.DEFAULT_MODEL
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"]["format"]["type"] == "json_schema"
    prompt = call["messages"][0]["content"]
    assert "graphs" in prompt
    assert "hard" in prompt
    assert "English" in call["system"]


def test_generate_problem_default_language_is_english():
    client = fake_client([{"title": "T", "statement": "S"}])
    llm.generate_problem("dp", client=client)
    assert "English" in client.messages.calls[0]["system"]


def test_review_solution_returns_feedback():
    client = fake_client(
        [{"verdict": "correct", "score": 9, "feedback": "Well done"}]
    )
    fb = llm.review_solution(
        problem_statement="Statement",
        solution_code="print(42)",
        run_stdout="42\n",
        run_stderr="",
        exit_code=0,
        timed_out=False,
        client=client,
    )
    assert fb.verdict == "correct"
    assert fb.score == 9
    assert fb.feedback == "Well done"


def test_review_solution_prompt_includes_context():
    client = fake_client(
        [{"verdict": "incorrect", "score": 3, "feedback": "..."}]
    )
    llm.review_solution(
        problem_statement="STATEMENT_MARKER",
        solution_code="CODE_MARKER",
        run_stdout="STDOUT_MARKER",
        run_stderr="STDERR_MARKER",
        exit_code=1,
        timed_out=True,
        client=client,
    )
    prompt = client.messages.calls[0]["messages"][0]["content"]
    for marker in ("STATEMENT_MARKER", "CODE_MARKER", "STDOUT_MARKER", "STDERR_MARKER"):
        assert marker in prompt
    assert "timed out: True" in prompt


def test_refusal_raises_llm_error():
    client = fake_client([{"title": "T", "statement": "S"}], stop_reason="refusal")
    with pytest.raises(llm.LLMError, match="refused"):
        llm.generate_problem("dp", client=client)


def test_invalid_json_raises_llm_error():
    from types import SimpleNamespace

    class BrokenMessages:
        def create(self, **kwargs):
            return SimpleNamespace(
                stop_reason="end_turn",
                content=[SimpleNamespace(type="text", text="not json")],
            )

    client = SimpleNamespace(messages=BrokenMessages())
    with pytest.raises(llm.LLMError, match="JSON"):
        llm.generate_problem("dp", client=client)


def test_missing_credentials_raises_llm_error():
    from types import SimpleNamespace

    class NoAuthMessages:
        def create(self, **kwargs):
            raise TypeError("Could not resolve authentication method. ...")

    client = SimpleNamespace(messages=NoAuthMessages())
    with pytest.raises(llm.LLMError, match="ANTHROPIC_API_KEY"):
        llm.generate_problem("dp", client=client)


def test_api_error_wrapped(monkeypatch):
    import anthropic

    class FailingMessages:
        def create(self, **kwargs):
            raise anthropic.APIConnectionError(request=None)

    from types import SimpleNamespace

    client = SimpleNamespace(messages=FailingMessages())
    with pytest.raises(llm.LLMError, match="failed"):
        llm.generate_problem("dp", client=client)
