"""Coverage-raising tests for app.services.weekly_summary.

Exercises the 24h cache gate (hit / stale-miss / force-refresh), the prompt
data-gathering path, JSON parse success + fallback, and markdown-fence
stripping. Groq is fully mocked — no network.
"""

import types
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.career import CareerTarget, TimelineEvent
from app.models.degree import Course, CourseStatus
from app.models.user import User
from app.services.auth import hash_password
from app.services.weekly_summary import CACHE_TTL, generate_weekly_summary


# ── Groq mock ────────────────────────────────────────────────────────

class _MockChoice:
    def __init__(self, content):
        self.message = types.SimpleNamespace(content=content)


class _MockCompletions:
    def __init__(self, content, on_call=None):
        self._content = content
        self._on_call = on_call

    def create(self, *args, **kwargs):
        if self._on_call:
            self._on_call()
        return types.SimpleNamespace(choices=[_MockChoice(self._content)])


class _MockGroqClient:
    def __init__(self, content, on_call=None):
        self.chat = types.SimpleNamespace(completions=_MockCompletions(content, on_call))


def _patch_groq(monkeypatch, content, on_call=None):
    monkeypatch.setattr(
        "app.services.weekly_summary.get_groq_client",
        lambda: _MockGroqClient(content, on_call),
    )


VALID_JSON = (
    '{"greeting": "This week is quiet.", "highlights": ["h1"],'
    ' "action_items": ["a1"], "motivation": "Keep going."}'
)


@pytest.fixture
async def summary_user(db):
    user = User(
        id=uuid.uuid4(),
        email="weekly@example.com",
        hashed_password=hash_password("testpass123"),
        full_name="Weekly User",
        university="Test University",
        program="Computer Science",
        career_target="Backend Engineering",
        expected_graduation_year=2028,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ── cache behaviour ──────────────────────────────────────────────────

async def test_cache_hit_returns_cached_without_calling_groq(summary_user, db, monkeypatch):
    summary_user.weekly_summary = {"greeting": "cached", "highlights": [], "action_items": [], "motivation": ""}
    summary_user.weekly_summary_generated_at = datetime.now(timezone.utc) - timedelta(hours=1)

    def _boom():
        raise AssertionError("Groq must not be called on a fresh cache hit")

    _patch_groq(monkeypatch, VALID_JSON, on_call=_boom)

    result = await generate_weekly_summary(summary_user, db)
    assert result["greeting"] == "cached"


async def test_stale_cache_triggers_regeneration(summary_user, db, monkeypatch):
    summary_user.weekly_summary = {"greeting": "old"}
    # Older than the TTL → must regenerate.
    summary_user.weekly_summary_generated_at = datetime.now(timezone.utc) - (CACHE_TTL + timedelta(hours=1))

    calls = []
    _patch_groq(monkeypatch, VALID_JSON, on_call=lambda: calls.append(1))

    result = await generate_weekly_summary(summary_user, db)
    assert calls == [1]
    assert result["greeting"] == "This week is quiet."
    # Cache was refreshed and stamped.
    assert summary_user.weekly_summary["greeting"] == "This week is quiet."
    assert summary_user.weekly_summary_generated_at is not None


async def test_force_refresh_bypasses_fresh_cache(summary_user, db, monkeypatch):
    summary_user.weekly_summary = {"greeting": "cached"}
    summary_user.weekly_summary_generated_at = datetime.now(timezone.utc)

    calls = []
    _patch_groq(monkeypatch, VALID_JSON, on_call=lambda: calls.append(1))

    result = await generate_weekly_summary(summary_user, db, force_refresh=True)
    assert calls == [1]
    assert result["greeting"] == "This week is quiet."


# ── prompt data gathering + response handling ────────────────────────

async def test_generates_from_real_data(summary_user, db, monkeypatch):
    # Seed in-progress course, a career target and an upcoming event so the
    # data-gathering branches (in_progress / targets / deadlines) all run.
    db.add(Course(
        user_id=summary_user.id, course_code="CS200", course_name="Data Structures",
        credit_value=3.0, status=CourseStatus.in_progress, term="Fall 2026",
    ))
    db.add(CareerTarget(user_id=summary_user.id, company_name="Acme", role_type="SWE Intern"))
    db.add(TimelineEvent(
        user_id=summary_user.id, title="Resume deadline",
        event_date=date(2026, 9, 1), category="deadline",
    ))
    await db.commit()

    _patch_groq(monkeypatch, VALID_JSON)
    result = await generate_weekly_summary(summary_user, db)
    assert result["greeting"] == "This week is quiet."
    assert result["action_items"] == ["a1"]
    # Persisted onto the user record.
    assert summary_user.weekly_summary == result


async def test_markdown_fenced_response_is_stripped(summary_user, db, monkeypatch):
    fenced = "```json\n" + VALID_JSON + "\n```"
    _patch_groq(monkeypatch, fenced)
    result = await generate_weekly_summary(summary_user, db)
    assert result["greeting"] == "This week is quiet."


async def test_unparseable_response_falls_back(summary_user, db, monkeypatch):
    _patch_groq(monkeypatch, "sorry, I could not comply")
    result = await generate_weekly_summary(summary_user, db)
    # Fallback envelope keeps the shape stable and stashes the raw text.
    assert result["greeting"] == "Your weekly check-in."
    assert result["highlights"] == []
    assert result["action_items"] == ["sorry, I could not comply"]
    assert "motivation" in result
