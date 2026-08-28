# STATUS

## Web application (added 2026-07-13)

The project is now a full web app alongside the CLI. Start it with
`interview-coach web` and open http://127.0.0.1:8000. Version bumped to 0.2.0.

**Backend** — `webapp.py`: FastAPI app that wraps the existing `llm.py` /
`db.py` / `runner.py` (no core logic was rewritten). Endpoints:
- `POST /api/problems` — generate a problem (`{topic, difficulty, lang}`), 201 + full problem; 502 if the LLM call fails;
- `GET /api/problems`, `GET /api/problems/{id}` — list (summaries) / detail with statement, 404 if missing;
- `POST /api/problems/{id}/attempts` — `{code, lang, timeout}`: writes the code to a temp file, runs it via `runner.run_solution`, asks Claude for a review, saves the attempt, returns verdict/score/feedback + stdout/stderr;
- `GET /api/attempts?problem_id=` — attempt history with problem titles;
- `/` — static frontend (mounted last so `/api/*` wins); interactive API docs at `/docs`.

**Frontend** — `static/` (vanilla HTML/CSS/JS, no build step): topic picker
with suggestion chips, difficulty segmented control, language select (en/uk),
rendered problem statement, code editor (tab support, ⌘/Ctrl+Enter submits),
verdict banner with score bar, Markdown feedback, collapsible run output, and
a History view with expandable past attempts. Light + dark theme via
`prefers-color-scheme`.

**Verification:** 12 new API tests in `tests/test_api.py` (FastAPI TestClient,
LLM mocked) — 44 tests total, all green. Also verified live end-to-end against
the real Anthropic API: served UI → `POST /api/problems` (real generation) →
`POST /api/problems/1/attempts` (real run + review, got 6/10 with fair
feedback) → history visible from both `GET /api/attempts` and the CLI
`history` command against the same database.

### Decisions worth knowing

1. **One `Database` per request** — sqlite3 objects must stay on one thread and FastAPI runs sync endpoints in a threadpool, so each request opens/closes its own connection (same pattern as one-connection-per-CLI-command).
2. **Web submissions run from a temp file** — `runner.run_solution` takes a path, so the posted code is written to a `TemporaryDirectory` and `solution_path` is stored as `"web"` in the DB. No schema changes.
3. **Attempt is saved even if the review call fails** (parity with the CLI); the response then carries `verdict: null` plus an `llm_error` message, and the UI shows "saved without review".
4. **Frontend is dependency-free** — Markdown is rendered client-side by a small escape-first renderer (all text is HTML-escaped before any tags are added, so model output can't inject HTML). No CDN, works offline.
5. **Language isn't persisted in the DB** — the UI remembers the en/uk choice in localStorage and sends it per request; the schema stays untouched.
6. **`fastapi` + `uvicorn` are main dependencies** (not an extra) to keep the one-command story: `pip install -e .` → `interview-coach web`.

## What's done

The MVP is fully complete and verified. The project lives in `interview-coach/`,
installed as a package with the console command `interview-coach`.

**CLI commands (click):**
- `new <topic>` — generates a problem via the Anthropic API (`-d easy|medium|hard`, `-l uk|en`), saves it to SQLite, prints the statement;
- `submit <problem_id> <file.py>` — runs the solution in a subprocess (15 s timeout, `--timeout`), shows stdout/stderr, sends the statement + code + run result to Claude and prints the verdict/score/feedback;
- `history` (`-p <id>`) — list of problems and attempts;
- `show <id>` — statement of a saved problem.

**Modules** (`src/interview_coach/`):
- `llm.py` — Anthropic SDK: problem generation and solution review;
- `runner.py` — runs the solution (`sys.executable`, timeout, output truncated to 20K characters);
- `db.py` — SQLite: `problems` and `attempts` tables (defaults to `~/.interview-coach/history.db`);
- `config.py` — custom `.env` parser (no python-dotenv dependency), paths, constants;
- `cli.py` — commands.

**Verification:**
- 32 tests, all green (`pytest`): db, runner, llm (mocks), CLI (CliRunner), wire-level integration;
- full e2e via the real binary against a fake local API server: `new → submit → history → show` — everything works, including a real run of a DP-problem solution.

## Key decisions and why

1. **Model `claude-opus-4-8` + `thinking: {"type": "adaptive"}`** — the current Anthropic API default; `budget_tokens` is no longer supported on this model.
2. **Structured responses via `output_config.format` (json_schema)** instead of parsing free-form text — the API guarantees valid JSON, so problem generation strictly returns `{title, statement}`, and feedback returns `{verdict, score, feedback}`. This eliminates an entire class of parsing errors.
3. **`.env` is parsed by a custom `load_dotenv()` function** (~15 lines) — not pulling in python-dotenv for a single file. Existing environment variables take priority over `.env`.
4. **Feedback and problem statements default to English** (`-l uk` for Ukrainian).
5. **The problem requires a script with no stdin** (a function plus a demonstration via `print`) — so `submit` can just run the file and show Claude the output without any interactivity.
6. **An attempt is saved even if the API call fails** — running the solution isn't wasted; it's marked "no feedback" in the history.
7. **The missing-credentials error is handled separately**: the SDK raises `TypeError` (not `APIError`); without handling it, the user saw a raw traceback — found during smoke testing, fixed to a clean message with a hint about `.env` (there's a test for it).
8. **Tests don't touch the network**: unit tests mock the client, and `test_integration.py` runs the real SDK through `httpx.MockTransport` — it verifies actual request serialization (model/thinking/output_config) and parsing of a real Messages API response without sockets. This is the most valuable test layer: it would catch a parameter incompatibility with the SDK version.

## Where I got stuck

1. **No `ANTHROPIC_API_KEY` in the environment or via an `ant` profile** — a live API request was never verified. The code is written for a key in `.env` (see `.env.example`); the entire wire path was verified with a fake server and MockTransport, so it should work unchanged once a key is provided.
2. **Background listening sockets don't work in this environment**: a fake HTTP server launched as a background shell process created a socket stuck in `CLOSED` state instead of `LISTEN` (even outside the sandbox) — the first e2e attempt timed out. Workaround: run the server in a thread of the parent Python process, with the CLI as its subprocess (`scratchpad/e2e_driver.py`). After that, the e2e run passed completely. This limitation doesn't reproduce on a normal machine.

## How to run

```bash
cd interview-coach
source .venv/bin/activate        # venv already created, package installed
cp .env.example .env             # fill in your ANTHROPIC_API_KEY
interview-coach web              # web UI at http://127.0.0.1:8000
# or the CLI:
interview-coach new dynamic-programming
interview-coach submit 1 solution.py
interview-coach history
pytest                           # 44 passed
```
