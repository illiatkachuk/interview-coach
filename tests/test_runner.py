"""Tests for running solutions."""

import pytest

from interview_coach.runner import MAX_OUTPUT_CHARS, run_solution


def test_successful_run(tmp_path):
    script = tmp_path / "ok.py"
    script.write_text("print('hello')\n")
    result = run_solution(script)
    assert result.ok
    assert result.exit_code == 0
    assert result.stdout.strip() == "hello"
    assert result.stderr == ""
    assert not result.timed_out


def test_failing_run(tmp_path):
    script = tmp_path / "bad.py"
    script.write_text("raise ValueError('boom')\n")
    result = run_solution(script)
    assert not result.ok
    assert result.exit_code != 0
    assert "ValueError: boom" in result.stderr
    assert not result.timed_out


def test_timeout(tmp_path):
    script = tmp_path / "slow.py"
    script.write_text("import time\ntime.sleep(60)\n")
    result = run_solution(script, timeout=1)
    assert result.timed_out
    assert not result.ok
    assert "interrupted" in result.stderr


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_solution(tmp_path / "nope.py")


def test_output_truncated(tmp_path):
    script = tmp_path / "spam.py"
    script.write_text(f"print('x' * {MAX_OUTPUT_CHARS * 2})\n")
    result = run_solution(script)
    assert result.ok
    assert len(result.stdout) < MAX_OUTPUT_CHARS + 100
    assert "truncated" in result.stdout
