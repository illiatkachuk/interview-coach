"""CLI-команди interview-coach (click)."""

import sys
from pathlib import Path

import click

from . import llm
from .config import DEFAULT_LANG, RUN_TIMEOUT_SECONDS, db_path, load_dotenv
from .db import Database
from .runner import run_solution

_VERDICT_LABELS = {
    "correct": "✅ правильно",
    "partially_correct": "🟡 частково правильно",
    "incorrect": "❌ неправильно",
}


@click.group()
def cli():
    """interview-coach — тренажер для технічних співбесід."""
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
    help="Складність задачі.",
)
@click.option(
    "--lang",
    "-l",
    default=DEFAULT_LANG,
    show_default=True,
    help="Мова умови задачі (uk/en).",
)
def new(topic: str, difficulty: str, lang: str):
    """Згенерувати нову задачу за темою (напр. dynamic-programming)."""
    click.echo(f"Генерую задачу з теми «{topic}» ({difficulty})…")
    try:
        problem = llm.generate_problem(topic, difficulty=difficulty, lang=lang)
    except llm.LLMError as exc:
        raise click.ClickException(str(exc))

    with _open_db() as db:
        problem_id = db.add_problem(topic, difficulty, problem["title"], problem["statement"])

    click.echo()
    click.secho(f"Задача #{problem_id}: {problem['title']}", bold=True)
    click.echo()
    click.echo(problem["statement"])
    click.echo()
    click.echo(
        f"Коли будете готові: interview-coach submit {problem_id} <ваш_файл.py>"
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
    help="Ліміт часу виконання розв'язку, секунд.",
)
@click.option(
    "--lang",
    "-l",
    default=DEFAULT_LANG,
    show_default=True,
    help="Мова фідбеку (uk/en).",
)
def submit(problem_id: int, solution_file: Path, timeout: int, lang: str):
    """Здати розв'язок: запустити файл і отримати фідбек від Claude."""
    with _open_db() as db:
        problem = db.get_problem(problem_id)
        if problem is None:
            raise click.ClickException(f"Задачі #{problem_id} не існує.")

        click.echo(f"Запускаю {solution_file}…")
        result = run_solution(solution_file, timeout=timeout)

        if result.timed_out:
            click.secho("⏱ Розв'язок перервано за таймаутом.", fg="yellow")
        elif result.exit_code != 0:
            click.secho(f"Розв'язок завершився з кодом {result.exit_code}.", fg="yellow")
        if result.stdout.strip():
            click.echo("--- stdout ---")
            click.echo(result.stdout.rstrip())
        if result.stderr.strip():
            click.echo("--- stderr ---")
            click.echo(result.stderr.rstrip())

        click.echo()
        click.echo("Запитую фідбек у Claude…")
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
            # Спробу все одно зберігаємо — без фідбеку.
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
                f"{exc}\nСпробу збережено в історії без фідбеку."
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
    click.secho(f"Спроба #{attempt_id}: {verdict_label}, оцінка {fb.score}/10", bold=True)
    click.echo()
    click.echo(fb.feedback)


@cli.command()
@click.option("--problem", "-p", "problem_id", type=int, default=None,
              help="Показати спроби лише для однієї задачі.")
def history(problem_id: int | None):
    """Показати історію задач і спроб."""
    with _open_db() as db:
        problems = db.list_problems()
        attempts = db.list_attempts(problem_id)

    if problem_id is None:
        if not problems:
            click.echo("Історія порожня. Почніть з: interview-coach new <тема>")
            return
        click.secho("Задачі:", bold=True)
        for p in problems:
            click.echo(
                f"  #{p['id']} [{p['topic']}/{p['difficulty']}] {p['title']} ({p['created_at']})"
            )
        click.echo()

    if attempts:
        click.secho("Спроби:", bold=True)
        for a in attempts:
            verdict = _VERDICT_LABELS.get(a["verdict"], a["verdict"] or "без фідбеку")
            score = f"{a['score']}/10" if a["score"] is not None else "—"
            click.echo(
                f"  #{a['id']} → задача #{a['problem_id']} «{a['problem_title']}»:"
                f" {verdict}, {score} ({a['created_at']})"
            )
    elif problem_id is not None:
        click.echo(f"Для задачі #{problem_id} спроб ще немає.")


@cli.command()
@click.argument("problem_id", type=int)
def show(problem_id: int):
    """Показати умову збереженої задачі."""
    with _open_db() as db:
        problem = db.get_problem(problem_id)
    if problem is None:
        raise click.ClickException(f"Задачі #{problem_id} не існує.")
    click.secho(
        f"Задача #{problem['id']} [{problem['topic']}/{problem['difficulty']}]:"
        f" {problem['title']}",
        bold=True,
    )
    click.echo()
    click.echo(problem["statement"])


def main() -> None:
    cli(prog_name="interview-coach")


if __name__ == "__main__":
    sys.exit(main())
