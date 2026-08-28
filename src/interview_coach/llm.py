"""Anthropic API integration: problem generation and solution feedback."""

import json
from dataclasses import dataclass

import anthropic

from .config import DEFAULT_LANG, DEFAULT_MODEL

_LANG_NAMES = {
    "uk": "Ukrainian",
    "en": "English",
}

PROBLEM_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Short problem title"},
        "statement": {
            "type": "string",
            "description": (
                "Full problem statement in Markdown: description, input/output "
                "format, constraints and at least two examples"
            ),
        },
    },
    "required": ["title", "statement"],
    "additionalProperties": False,
}

FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["correct", "partially_correct", "incorrect"],
            "description": "Overall correctness of the solution",
        },
        "score": {
            "type": "integer",
            "enum": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "description": "Interview-style score from 1 (poor) to 10 (excellent)",
        },
        "feedback": {
            "type": "string",
            "description": (
                "Concise interview-style feedback in Markdown: correctness, "
                "complexity, code quality, and one concrete improvement"
            ),
        },
    },
    "required": ["verdict", "score", "feedback"],
    "additionalProperties": False,
}


class LLMError(RuntimeError):
    """Error while calling the Anthropic API."""


@dataclass
class Feedback:
    verdict: str
    score: int
    feedback: str


def _language(lang: str) -> str:
    return _LANG_NAMES.get(lang, _LANG_NAMES[DEFAULT_LANG])


def _structured_request(client: anthropic.Anthropic, system: str, prompt: str, schema: dict) -> dict:
    """A single request to Claude with a structured JSON response."""
    try:
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
    except anthropic.APIError as exc:
        raise LLMError(f"Anthropic API request failed: {exc}") from exc
    except TypeError as exc:
        # The SDK raises TypeError when no authentication method is found.
        if "authentication" in str(exc).lower():
            raise LLMError(
                "No Anthropic credentials found. Add ANTHROPIC_API_KEY "
                "to .env (see .env.example) or to your environment variables."
            ) from exc
        raise

    if response.stop_reason == "refusal":
        raise LLMError("The model refused to respond to this request.")
    if response.stop_reason == "max_tokens":
        raise LLMError("The response was truncated due to the token limit — try again.")

    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise LLMError("The model's response has no text block.")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Failed to parse JSON from the model's response: {exc}") from exc


def generate_problem(
    topic: str,
    difficulty: str = "medium",
    lang: str = DEFAULT_LANG,
    client: anthropic.Anthropic | None = None,
) -> dict:
    """Generates an interview problem on a topic. Returns {"title", "statement"}."""
    client = client or anthropic.Anthropic()
    system = (
        "You are a senior software engineer preparing coding-interview problems. "
        f"Write the problem in {_language(lang)}."
    )
    prompt = (
        f"Create one {difficulty}-difficulty coding interview problem on the topic "
        f'"{topic}".\n'
        "Requirements:\n"
        "- solvable in plain Python without third-party libraries;\n"
        "- the candidate's script must read nothing from stdin: it should define "
        "a function and demonstrate it on the provided examples via print();\n"
        "- include input/output format, constraints, and at least two worked "
        "examples with expected output;\n"
        "- do NOT include the solution."
    )
    data = _structured_request(client, system, prompt, PROBLEM_SCHEMA)
    return {"title": data["title"], "statement": data["statement"]}


def review_solution(
    problem_statement: str,
    solution_code: str,
    run_stdout: str,
    run_stderr: str,
    exit_code: int,
    timed_out: bool,
    lang: str = DEFAULT_LANG,
    client: anthropic.Anthropic | None = None,
) -> Feedback:
    """Asks Claude to evaluate a solution; returns Feedback(verdict, score, feedback)."""
    client = client or anthropic.Anthropic()
    system = (
        "You are an experienced technical interviewer reviewing a candidate's "
        f"solution. Give honest, specific, concise feedback in {_language(lang)}."
    )
    run_summary = (
        f"exit code: {exit_code}, timed out: {timed_out}\n"
        f"--- stdout ---\n{run_stdout or '(empty)'}\n"
        f"--- stderr ---\n{run_stderr or '(empty)'}"
    )
    prompt = (
        "## Problem\n"
        f"{problem_statement}\n\n"
        "## Candidate's solution (Python)\n"
        f"```python\n{solution_code}\n```\n\n"
        "## Execution result\n"
        f"{run_summary}\n\n"
        "Evaluate correctness against the problem (including the printed output), "
        "time/space complexity, and code quality. Point out the single most "
        "important improvement."
    )
    data = _structured_request(client, system, prompt, FEEDBACK_SCHEMA)
    return Feedback(verdict=data["verdict"], score=data["score"], feedback=data["feedback"])
