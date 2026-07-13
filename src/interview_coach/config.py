"""Конфігурація: завантаження .env та значення за замовчуванням."""

import os
from pathlib import Path

DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_DB_PATH = Path.home() / ".interview-coach" / "history.db"
DEFAULT_LANG = "uk"
RUN_TIMEOUT_SECONDS = 15


def load_dotenv(path: Path | None = None) -> None:
    """Читає KEY=VALUE з .env у os.environ, не перезаписуючи наявні змінні.

    Шукає .env у поточній директорії, якщо шлях не передано явно.
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
    """Шлях до бази: INTERVIEW_COACH_DB або ~/.interview-coach/history.db."""
    override = os.environ.get("INTERVIEW_COACH_DB")
    return Path(override) if override else DEFAULT_DB_PATH
