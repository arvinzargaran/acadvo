"""Reading a model's text output.

These pin the behaviour that broke every AI feature at once when the configured
Groq model was swapped: the JSON paths used to do ``content.strip()`` plus a
markdown-fence check inline, which is correct for a non-reasoning model and
silently wrong for one that writes ``<think>`` into the content itself. The
symptom was "the AI response was not valid JSON", reported to the student as a
problem with the document they had just uploaded.
"""
import pytest

from app.ai.client import (
    budget_max_tokens,
    clean_model_text,
    completion_text,
    vision_kwargs,
)
from app.config import settings


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Msg(content)


class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]


def test_plain_json_passes_through():
    assert clean_model_text('{"a": 1}') == '{"a": 1}'


def test_think_block_is_removed():
    raw = '<think>\nFirst I should enumerate the buckets.\n</think>\n[{"code": "EECS 1012"}]'
    assert clean_model_text(raw) == '[{"code": "EECS 1012"}]'


def test_think_block_before_a_fence():
    raw = '<think>reasoning</think>\n```json\n{"a": 1}\n```'
    assert clean_model_text(raw) == '{"a": 1}'


def test_multiple_think_blocks():
    raw = '<think>one</think>{"a": 1}<think>two</think>'
    assert clean_model_text(raw) == '{"a": 1}'


def test_unclosed_think_block_yields_nothing():
    """Generation hit the token cap while still reasoning.

    There is no answer after an unterminated block, and returning the monologue
    would hand a paragraph of prose to json.loads. Empty is the honest result —
    it is also what the vision model did on a real checklist image before
    reasoning was turned off for it.
    """
    assert clean_model_text("<think>still thinking when the budget ran out") == ""


def test_fence_without_language_tag():
    assert clean_model_text("```\n[1, 2]\n```") == "[1, 2]"


def test_prose_paths_keep_their_fences():
    """The chat reply and the recommendation blurb are prose.

    A fenced code block there is content the student asked for; unwrapping it
    would corrupt the answer. Only the reasoning block is unwanted.
    """
    raw = '<think>plan the answer</think>Here is the snippet:\n```python\nprint(1)\n```'
    cleaned = clean_model_text(raw, strip_fence=False)
    assert cleaned.startswith("Here is the snippet:")
    assert "```python" in cleaned


def test_none_and_empty_are_safe():
    assert clean_model_text(None) == ""
    assert clean_model_text("") == ""


def test_completion_text_reads_a_response():
    assert completion_text(_Response('<think>x</think>{"a": 1}')) == '{"a": 1}'


def test_completion_text_on_a_malformed_response():
    """A response with no choices must not raise inside a request handler."""

    class _Empty:
        choices = []

    assert completion_text(_Empty()) == ""


def test_vision_kwargs_follow_the_setting(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_VISION_REASONING_EFFORT", "none")
    assert vision_kwargs() == {"reasoning_effort": "none"}
    # Empty means "do not send the parameter at all" — models that reject it
    # outright fail the whole call otherwise.
    monkeypatch.setattr(settings, "GROQ_VISION_REASONING_EFFORT", "")
    assert vision_kwargs() == {}


# ── Request budgeting ────────────────────────────────────────────────


def test_budget_is_untouched_without_a_ceiling(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_MAX_REQUEST_TOKENS", 0)
    assert budget_max_tokens("a" * 5000, 8192) == 8192


def test_budget_is_trimmed_to_fit_the_ceiling(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_MAX_REQUEST_TOKENS", 8000)
    prompt = "a" * 3000  # ~1000 estimated prompt tokens + 200 margin
    trimmed = budget_max_tokens(prompt, 8192)
    assert trimmed < 8192
    assert trimmed + (len(prompt) // 3 + 200) <= 8000


def test_budget_is_untouched_when_it_already_fits(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_MAX_REQUEST_TOKENS", 32000)
    assert budget_max_tokens("a" * 3000, 8192) == 8192


def test_budget_never_returns_an_unusable_stub(monkeypatch):
    """A prompt that alone exceeds the ceiling cannot be rescued by trimming.

    Returning 0 or a negative budget would be rejected by the SDK as a bad
    request, which is a confusing way to report "your account cannot serve a
    prompt this size". The floor lets the call go out and lets the provider's
    own rate-limit error surface, which main.py turns into an honest 429.
    """
    monkeypatch.setattr(settings, "GROQ_MAX_REQUEST_TOKENS", 1000)
    assert budget_max_tokens("a" * 90000, 8192) == 1500
