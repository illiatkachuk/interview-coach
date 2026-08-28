"""Runs the user's solution in a separate process."""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .config import RUN_TIMEOUT_SECONDS

# Truncate output so it doesn't bloat the DB or the feedback prompt.
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
    return text[:MAX_OUTPUT_CHARS] + "\n... [output truncated]"


def run_solution(path: Path | str, timeout: int = RUN_TIMEOUT_SECONDS) -> RunResult:
    """Runs a Python file with the current interpreter and collects its output."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Solution file not found: {path}")
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
            stderr=_truncate(stderr + f"\n[interrupted: exceeded the {timeout}s limit]"),
            exit_code=-1,
            timed_out=True,
        )
    return RunResult(
        stdout=_truncate(proc.stdout),
        stderr=_truncate(proc.stderr),
        exit_code=proc.returncode,
        timed_out=False,
    )
