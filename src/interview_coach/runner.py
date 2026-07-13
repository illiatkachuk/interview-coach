"""Запуск розв'язку користувача в окремому процесі."""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .config import RUN_TIMEOUT_SECONDS

# Обрізаємо вивід, щоб не роздувати БД і промпт для фідбеку.
MAX_OUTPUT_CHARS = 20_000


@dataclass
class RunResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n... [вивід обрізано]"


def run_solution(path: Path | str, timeout: int = RUN_TIMEOUT_SECONDS) -> RunResult:
    """Виконує python-файл поточним інтерпретатором і збирає вивід."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Файл розв'язку не знайдено: {path}")
    try:
        proc = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return RunResult(
            stdout=_truncate(stdout),
            stderr=_truncate(stderr + f"\n[перервано: перевищено ліміт {timeout} c]"),
            exit_code=-1,
            timed_out=True,
        )
    return RunResult(
        stdout=_truncate(proc.stdout),
        stderr=_truncate(proc.stderr),
        exit_code=proc.returncode,
        timed_out=False,
    )
