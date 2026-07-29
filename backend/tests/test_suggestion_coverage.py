"""Coverage-raising tests for app.services.suggestion.

Covers pending-list filtering + ordering, accept/reject persistence, and the
two 404 branches (missing id, wrong owner).
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.models.suggestion import AISuggestion, RiskSeverity, SuggestionType
from app.models.user import User
from app.services.auth import hash_password
from app.services.suggestion import list_pending_suggestions, update_suggestion


async def _make_user(db, email):
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password("testpass123"),
        full_name="Sug User",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def sug_user(db):
    return await _make_user(db, "sug@example.com")


def _add_suggestion(db, user_id, content, *, accepted=None, created_at=None,
                    stype=SuggestionType.course, severity=None):
    s = AISuggestion(
        id=uuid.uuid4(),
        user_id=user_id,
        suggestion_type=stype,
        content=content,
        severity=severity,
        accepted=accepted,
    )
    if created_at is not None:
        s.created_at = created_at
    db.add(s)
    return s


async def test_list_pending_only_returns_undecided_ordered_newest_first(sug_user, db):
    now = datetime.now(timezone.utc)
    _add_suggestion(db, sug_user.id, "older pending", created_at=now - timedelta(hours=2))
    _add_suggestion(db, sug_user.id, "newer pending", created_at=now - timedelta(hours=1))
    _add_suggestion(db, sug_user.id, "accepted", accepted=True)
    _add_suggestion(db, sug_user.id, "rejected", accepted=False)
    await db.commit()

    pending = await list_pending_suggestions(sug_user.id, db)
    contents = [s.content for s in pending]
    # Decided suggestions excluded; pending ordered newest → oldest.
    assert contents == ["newer pending", "older pending"]


async def test_list_pending_is_scoped_per_user(sug_user, db):
    other = await _make_user(db, "other@example.com")
    _add_suggestion(db, sug_user.id, "mine")
    _add_suggestion(db, other.id, "theirs")
    await db.commit()

    mine = await list_pending_suggestions(sug_user.id, db)
    assert [s.content for s in mine] == ["mine"]


async def test_update_suggestion_accept_then_reject(sug_user, db):
    s = _add_suggestion(db, sug_user.id, "risk", stype=SuggestionType.risk_flag,
                        severity=RiskSeverity.high)
    await db.commit()

    accepted = await update_suggestion(s.id, sug_user.id, True, db)
    assert accepted.accepted is True
    # Once decided it drops out of the pending list.
    assert await list_pending_suggestions(sug_user.id, db) == []

    rejected = await update_suggestion(s.id, sug_user.id, False, db)
    assert rejected.accepted is False


async def test_update_suggestion_missing_id_raises_404(sug_user, db):
    with pytest.raises(HTTPException) as exc:
        await update_suggestion(uuid.uuid4(), sug_user.id, True, db)
    assert exc.value.status_code == 404


async def test_update_suggestion_wrong_owner_raises_404(sug_user, db):
    other = await _make_user(db, "intruder@example.com")
    s = _add_suggestion(db, sug_user.id, "not yours")
    await db.commit()

    # Another user must not be able to accept someone else's suggestion.
    with pytest.raises(HTTPException) as exc:
        await update_suggestion(s.id, other.id, True, db)
    assert exc.value.status_code == 404

    # And the row is untouched.
    await db.refresh(s)
    assert s.accepted is None
