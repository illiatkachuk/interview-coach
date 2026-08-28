"""interview-coach CLI commands (click)."""

import sys
from pathlib import Path

import click

from . import llm
from .config import DEFAULT_LANG, RUN_TIMEOUT_SECONDS, db_path, load_dotenv
from .db import Database
from .runner import run_solution

_VERDICT_LABELS = {
    "correct": "✅ correct",
    "partially_correct": "🟡 partially correct",
    "incorrect": "❌ incorrect",
}


@click.group()
def cli():
    """interview-coach — a trainer for technical interviews."""
    load_dotenv()


def _open_db() -> Database:
    return Database(db_path())


@cli.command()
@click.argument("topic")
@click.option(
    "--difficulty",
    "-d",
    type=click.Choice(["easy", "medium", "hard"]),
    default="medium",
    show_default=True,
    help="Problem difficulty.",
)
@click.option(
    "--lang",
    "-l",
    default=DEFAULT_LANG,
    show_default=True,
    help="Problem statement language (uk/en).",
)
def new(topic: str, difficulty: str, lang: str):
    """Generate a new problem on a topic (e.g. dynamic-programming)."""
    click.echo(f'Generating a problem on topic "{topic}" ({difficulty})…')
    try:
        problem = llm.generate_problem(topic, difficulty=difficulty, lang=lang)
    except llm.LLMError as exc:
        raise click.ClickException(str(exc))

    with _open_db() as db:
        problem_id = db.add_problem(topic, difficulty, problem["title"], problem["statement"])

    click.echo()
    click.secho(f"Problem #{problem_id}: {problem['title']}", bold=True)
    click.echo()
    click.echo(problem["statement"])
    click.echo()
    click.echo(
        f"When ready: interview-coach submit {problem_id} <your_file.py>"
    )


@cli.command()
@click.argument("problem_id", type=int)
@click.argument(
    "solution_file", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option(
    "--timeout",
    type=int,
    default=RUN_TIMEOUT_SECONDS,
    show_default=True,
    help="Solution execution time limit, in seconds.",
)
@click.option(
    "--lang",
    "-l",
    default=DEFAULT_LANG,
    show_default=True,
    help="Feedback language (uk/en).",
)
def submit(problem_id: int, solution_file: Path, timeout: int, lang: str):
    """Submit a solution: run the file and get feedback from Claude."""
    with _open_db() as db:
        problem = db.get_problem(problem_id)
        if problem is None:
            raise click.ClickException(f"Problem #{problem_id} does not exist.")

        click.echo(f"Running {solution_file}…")
        result = run_solution(solution_file, timeout=timeout)

        if result.timed_out:
            click.secho("⏱ Solution was interrupted by timeout.", fg="yellow")
        elif result.exit_code != 0:
            click.secho(f"Solution exited with code {result.exit_code}.", fg="yellow")
        if result.stdout.strip():
            click.echo("--- stdout ---")
            click.echo(result.stdout.rstrip())
        if result.stderr.strip():
            click.echo("--- stderr ---")
            click.echo(result.stderr.rstrip())

        click.echo()
        click.echo("Requesting feedback from Claude…")
        solution_code = solution_file.read_text(encoding="utf-8")
        try:
            fb = llm.review_solution(
                problem_statement=problem["statement"],
                solution_code=solution_code,
                run_stdout=result.stdout,
                run_stderr=result.stderr,
                exit_code=result.exit_code,
                timed_out=result.timed_out,
                lang=lang,
            )
        except llm.LLMError as exc:
            # Save the attempt anyway — without feedback.
            db.add_attempt(
                problem_id,
                str(solution_file),
                solution_code,
                result.stdout,
                result.stderr,
                result.exit_code,
                result.timed_out,
                verdict=None,
                score=None,
                feedback=None,
            )
            raise click.ClickException(
                f"{exc}\nThe attempt was saved to history without feedback."
            )

        attempt_id = db.add_attempt(
            problem_id,
            str(solution_file),
            solution_code,
            result.stdout,
            result.stderr,
            result.exit_code,
            result.timed_out,
            verdict=fb.verdict,
            score=fb.score,
            feedback=fb.feedback,
        )

    click.echo()
    verdict_label = _VERDICT_LABELS.get(fb.verdict, fb.verdict)
    click.secho(f"Attempt #{attempt_id}: {verdict_label}, score {fb.score}/10", bold=True)
    click.echo()
    click.echo(fb.feedback)


@cli.command()
@click.option("--problem", "-p", "problem_id", type=int, default=None,
              help="Show attempts for a single problem only.")
def history(problem_id: int | None):
    """Show the history of problems and attempts."""
    with _open_db() as db:
        problems = db.list_problems()
        attempts = db.list_attempts(problem_id)

    if problem_id is None:
        if not problems:
            click.echo("History is empty. Start with: interview-coach new <topic>")
            return
        click.secho("Problems:", bold=True)
        for p in problems:
            click.echo(
                f"  #{p['id']} [{p['topic']}/{p['difficulty']}] {p['title']} ({p['created_at']})"
            )
        click.echo()

    if attempts:
        click.secho("Attempts:", bold=True)
        for a in attempts:
            verdict = _VERDICT_LABELS.get(a["verdict"], a["verdict"] or "no feedback")
            score = f"{a['score']}/10" if a["score"] is not None else "—"
            click.echo(
                f"  #{a['id']} → problem #{a['problem_id']} \"{a['problem_title']}\":"
                f" {verdict}, {score} ({a['created_at']})"
            )
    elif problem_id is not None:
        click.echo(f"No attempts yet for problem #{problem_id}.")


@cli.command()
@click.argument("problem_id", type=int)
def show(problem_id: int):
    """Show the statement of a saved problem."""
    with _open_db() as db:
        problem = db.get_problem(problem_id)
    if problem is None:
        raise click.ClickException(f"Problem #{problem_id} does not exist.")
    click.secho(
        f"Problem #{problem['id']} [{problem['topic']}/{problem['difficulty']}]:"
        f" {problem['title']}",
        bold=True,
    )
    click.echo()
    click.echo(problem["statement"])


@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Interface to bind.")
@click.option("--port", default=8000, show_default=True, type=int, help="Port to listen on.")
def web(host: str, port: int):
    """Start the web app (browser UI + REST API)."""
    import uvicorn

    click.echo(f"interview-coach web app: http://{host}:{port}")
    uvicorn.run("interview_coach.webapp:app", host=host, port=port)


def main() -> None:
    cli(prog_name="interview-coach")


if __name__ == "__main__":
    sys.exit(main())
