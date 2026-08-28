"""Wire-level integration tests: real SDK + httpx.MockTransport.

Verify that our parameters (output_config, thinking) are serialized
correctly by the real SDK and that we correctly parse a real Messages API
response. No network access required.
"""

import json

import anthropic
import httpx

from interview_coach import llm

PROBLEM_PAYLOAD = {"title": "Minimum Coins", "statement": "# Statement\n..."}
FEEDBACK_PAYLOAD = {"verdict": "correct", "score": 9, "feedback": "Good DP."}


def _make_client(captured: list) -> anthropic.Anthropic:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured.append(body)
        schema_props = (
            body.get("output_config", {})
            .get("format", {})
            .get("schema", {})
            .get("properties", {})
        )
        payload = FEEDBACK_PAYLOAD if "verdict" in schema_props else PROBLEM_PAYLOAD
        message = {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": body["model"],
            "content": [
                {"type": "text", "text": json.dumps(payload, ensure_ascii=False)}
            ],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 100, "output_tokens": 200},
        }
        return httpx.Response(200, json=message)

    return anthropic.Anthropic(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_generate_problem_over_the_wire():
    captured = []
    client = _make_client(captured)
    problem = llm.generate_problem("dynamic-programming", client=client)
    assert problem == PROBLEM_PAYLOAD

    body = captured[0]
    assert body["model"] == llm.DEFAULT_MODEL
    assert body["thinking"] == {"type": "adaptive"}
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert "dynamic-programming" in body["messages"][0]["content"]


def test_review_solution_over_the_wire():
    captured = []
    client = _make_client(captured)
    fb = llm.review_solution(
        problem_statement="Statement",
        solution_code="print(3)",
        run_stdout="3\n",
        run_stderr="",
        exit_code=0,
        timed_out=False,
        client=client,
    )
    assert fb.verdict == "correct"
    assert fb.score == 9
    assert fb.feedback == "Good DP."
    assert "print(3)" in captured[0]["messages"][0]["content"]
