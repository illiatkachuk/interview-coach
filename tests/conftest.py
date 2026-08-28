"""Shared fixtures: temporary DB and a mocked Anthropic client."""

import json
from types import SimpleNamespace

import pytest

from interview_coach.db import Database


@pytest.fixture
def db(tmp_path):
    with Database(tmp_path / "test.db") as database:
        yield database


class FakeMessages:
    """Mock of client.messages: returns pre-baked JSON responses in order."""

    def __init__(self, payloads, stop_reason="end_turn"):
        self._payloads = list(payloads)
        self._stop_reason = stop_reason
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = self._payloads.pop(0)
        text_block = SimpleNamespace(type="text", text=json.dumps(payload))
        return SimpleNamespace(
            stop_reason=self._stop_reason,
            content=[text_block],
        )


def fake_client(payloads, stop_reason="end_turn"):
    """Creates an object with the anthropic.Anthropic().messages.create interface."""
    return SimpleNamespace(messages=FakeMessages(payloads, stop_reason=stop_reason))
