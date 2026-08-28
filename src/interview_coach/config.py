"""Configuration: .env loading and default values."""

import os
from pathlib import Path

DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_DB_PATH = Path.home() / ".interview-coach" / "history.db"
DEFAULT_LANG = "en"
RUN_TIMEOUT_SECONDS = 15


def load_dotenv(path: Path | None = None) -> None:
    """Reads KEY=VALUE pairs from .env into os.environ without overwriting existing variables.

    Looks for .env in the current directory if no path is given explicitly.
    """
    env_path = path if path is not None else Path.cwd() / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            os.environ.setdefault(key, value)


def db_path() -> Path:
    """Path to the database: INTERVIEW_COACH_DB or ~/.interview-coach/history.db."""
    override = os.environ.get("INTERVIEW_COACH_DB")
    return Path(override) if override else DEFAULT_DB_PATH
