# interview-coach

CLI-тренажер для технічних співбесід: генерує задачі через Anthropic API,
запускає ваш розв'язок і дає короткий фідбек від Claude. Історія спроб
зберігається в SQLite (`~/.interview-coach/history.db`).

## Встановлення

```bash
cd interview-coach
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Створіть `.env` із ключем (див. `.env.example`):

```bash
cp .env.example .env
# впишіть свій ANTHROPIC_API_KEY
```

## Використання

```bash
# 1. Згенерувати задачу за темою
interview-coach new dynamic-programming
interview-coach new graphs -d hard -l en

# 2. Написати розв'язок у файл і здати його
interview-coach submit 1 solution.py

# 3. Подивитися умову та історію
interview-coach show 1
interview-coach history
interview-coach history -p 1
```

`submit` запускає файл поточним інтерпретатором Python (таймаут 15 c,
змінюється через `--timeout`), показує stdout/stderr і надсилає умову,
код та результат запуску Claude для оцінки (вердикт, бал 1–10, фідбек).

## Тести

```bash
pytest
```

Тести не звертаються до API — Anthropic-клієнт замокано.

## Змінні оточення

| Змінна | Призначення |
|---|---|
| `ANTHROPIC_API_KEY` | Ключ Anthropic API (обов'язково для `new`/`submit`) |
| `INTERVIEW_COACH_DB` | Власний шлях до SQLite-бази історії |
