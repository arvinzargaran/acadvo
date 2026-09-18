"""The Groq client is constructed with bounded time limits.

Left at the SDK's defaults (60s per call, 2 automatic retries), a single model
call compounds with the app's own retry loop — `AI_MAX_ATTEMPTS` = 3 attempts in
`ai/conversation.py`, each of which the SDK would retry twice more — into roughly
nine minutes of wall clock. A chat turn makes up to `MAX_TOOL_ROUNDS` = 10 such
calls, and every one of them holds a thread from anyio's 40-slot pool while it
waits. A *slow* Groq (not even a failed one) is therefore enough to exhaust the
pool and stall requests that have nothing to do with AI.

Nothing else in the suite would notice if those arguments were dropped in a
refactor: the failure only shows up under a degraded provider, in production.
"""
import pytest

import app.ai.client as ai_client
from app.config import settings


@pytest.fixture
def captured_client_kwargs(monkeypatch):
    """Build a client through the real factory, capturing the constructor args."""
    captured: dict = {}

    class _FakeGroq:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(ai_client, "Groq", _FakeGroq)
    # The factory memoises; a client left over from another test would make this
    # assert nothing at all.
    monkeypatch.setattr(ai_client, "_client", None)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key-not-a-placeholder")
    ai_client._breaker.record_success()

    ai_client.get_groq_client()
    return captured


def test_client_has_a_bounded_per_call_timeout(captured_client_kwargs):
    timeout = captured_client_kwargs.get("timeout")
    assert timeout is not None, "Groq client must set an explicit timeout"
    assert 0 < float(timeout) <= 60, (
        "a per-call timeout above 60s reintroduces the thread-pool stall this "
        f"bounds; got {timeout}"
    )


def test_sdk_does_not_retry_on_top_of_the_apps_own_retry_loop(captured_client_kwargs):
    # Retrying in two places multiplies: the app's 3 attempts each become 3.
    assert captured_client_kwargs.get("max_retries") == 0
