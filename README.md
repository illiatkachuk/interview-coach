# interview-coach

Trainer for technical interviews with a web UI and a CLI: generates problems
via the Anthropic API, runs your solution, and gives short feedback from
Claude. Attempt history is stored in SQLite (`~/.interview-coach/history.db`),
shared between the web app and the CLI.

## Installation

```bash
cd interview-coach
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Create a `.env` file with your key (see `.env.example`):

```bash
cp .env.example .env
# fill in your ANTHROPIC_API_KEY
```

## Web app

```bash
interview-coach web
```

Then open <http://127.0.0.1:8000>. The flow: pick a topic → get a generated
problem → write or paste a solution → submit → see the verdict, score, and
feedback → browse past attempts under **History**. Options: `--host`, `--port`.

The web app is a FastAPI backend over the same core modules the CLI uses;
the REST API lives under `/api/*` (interactive docs at `/docs`).

## CLI usage

```bash
# 1. Generate a problem on a topic
interview-coach new dynamic-programming
interview-coach new graphs -d hard -l uk

# 2. Write a solution to a file and submit it
interview-coach submit 1 solution.py

# 3. View the statement and history
interview-coach show 1
interview-coach history
interview-coach history -p 1
```

`submit` runs the file with the current Python interpreter (15 s timeout,
adjustable via `--timeout`), shows stdout/stderr, and sends the statement,
code, and run result to Claude for evaluation (verdict, score 1-10, feedback).

## Tests

```bash
pytest
```

Tests don't reach the API — the Anthropic client is mocked.

## Environment variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key (required for `new`/`submit`) |
| `INTERVIEW_COACH_DB` | Custom path to the SQLite history database |
