"""A rate limit is a stated wait, not a blip to back off from.

Groq's free tier allows 8,000 tokens per minute. One advisor turn that calls a
tool spends roughly 4,000 answering and another 5,000 on the follow-up, so the
second call cannot fit in the same minute and comes back with the exact number
of seconds until the window reopens. Exponential backoff starting at half a
second burned all three attempts inside two seconds and returned 503 every
time — the tool loop, which is the product's headline feature, never completed
a single turn on the free tier.
"""

import pytest

from app.ai.conversation import (
    AI_MAX_PROVIDER_DELAY,
    _provider_retry_delay,
)


class _FakeResponse:
    def __init__(self, headers):
        self.headers = headers


class _FakeError(Exception):
    def __init__(self, message, headers=None):
        super().__init__(message)
        if headers is not None:
            self.response = _FakeResponse(headers)


GROQ_429 = (
    "Error code: 429 - {'error': {'message': 'Rate limit reached for model "
    "`openai/gpt-oss-120b` in organization `org_x` service tier `on_demand` on "
    "tokens per minute (TPM): Limit 8000, Used 5329, Requested 5420. Please try "
    "again in 20.6175s. Need more tokens? Upgrade to Dev Tier'}}"
)


def test_parses_the_delay_out_of_a_real_groq_rate_limit_message():
    assert _provider_retry_delay(_FakeError(GROQ_429)) == pytest.approx(20.6175)


def test_prefers_the_retry_after_header_over_the_message():
    exc = _FakeError(GROQ_429, headers={"retry-after": "7"})
    assert _provider_retry_delay(exc) == pytest.approx(7.0)


def test_header_casing_does_not_matter():
    exc = _FakeError("no delay in this text", headers={"Retry-After": "3.5"})
    assert _provider_retry_delay(exc) == pytest.approx(3.5)


def test_an_unparseable_header_falls_back_to_the_message():
    exc = _FakeError(GROQ_429, headers={"retry-after": "not-a-number"})
    assert _provider_retry_delay(exc) == pytest.approx(20.6175)


def test_returns_none_when_the_provider_said_nothing():
    assert _provider_retry_delay(_FakeError("connection reset by peer")) is None
    assert _provider_retry_delay(_FakeError("500 internal server error")) is None


def test_the_cap_is_high_enough_to_cover_a_full_free_tier_window():
    """A minute-long budget can state a delay near 60s only if it just reset; the
    observed values sit around 20s. The cap must clear those comfortably while
    still bounding a pathological value."""
    assert AI_MAX_PROVIDER_DELAY >= 21.0
