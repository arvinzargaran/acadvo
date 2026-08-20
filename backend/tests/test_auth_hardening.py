"""The parts of authentication that only matter when someone is attacking.

`test_auth.py` covers the happy paths — register, log in, refresh, log out. What
had no coverage at all was everything the service does when it is *not* a normal
user on the other end: per-account lockout, refresh-token replay detection, and
the deliberate refusal to leak whether an address is registered. Those are the
behaviours most likely to be quietly weakened by a later refactor, because
nothing about the app looks broken when they stop working.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import RefreshToken, User
from app.services.auth import (
    LOGIN_ATTEMPTS_BEFORE_THROTTLE,
    authenticate_user,
    create_refresh_token,
    hash_password,
    refresh_access_token,
    revoke_all_refresh_tokens,
)

PASSWORD = "CorrectHorseBattery9!"


async def _user(db, email=None):
    u = User(
        id=uuid.uuid4(),
        email=email or f"{uuid.uuid4().hex[:10]}@example.com",
        hashed_password=hash_password(PASSWORD),
        full_name="Auth Tester",
        email_verified=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


# ── Per-account lockout ──────────────────────────────────────────────


async def test_repeated_failures_lock_the_account(db):
    """A per-IP rate limit does nothing against a botnet; this is the other half."""
    user = await _user(db)
    for _ in range(LOGIN_ATTEMPTS_BEFORE_THROTTLE):
        with pytest.raises(HTTPException):
            await authenticate_user(user.email, "wrong-password", db)

    await db.refresh(user)
    assert user.failed_login_attempts >= LOGIN_ATTEMPTS_BEFORE_THROTTLE
    assert user.login_locked_until is not None


async def test_a_locked_account_rejects_even_the_right_password(db):
    user = await _user(db)
    for _ in range(LOGIN_ATTEMPTS_BEFORE_THROTTLE):
        with pytest.raises(HTTPException):
            await authenticate_user(user.email, "wrong-password", db)

    with pytest.raises(HTTPException) as exc:
        await authenticate_user(user.email, PASSWORD, db)
    # Same 401 and same wording as a wrong password: saying "locked" would
    # confirm the address is registered and tell an attacker they are landing.
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid email or password"


async def test_lockout_expiry_lets_the_owner_back_in(db):
    user = await _user(db)
    for _ in range(LOGIN_ATTEMPTS_BEFORE_THROTTLE):
        with pytest.raises(HTTPException):
            await authenticate_user(user.email, "wrong-password", db)

    await db.refresh(user)
    user.login_locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db.commit()

    ok = await authenticate_user(user.email, PASSWORD, db)
    assert ok.id == user.id


async def test_a_good_login_clears_the_failure_counter(db):
    user = await _user(db)
    with pytest.raises(HTTPException):
        await authenticate_user(user.email, "wrong-password", db)

    await authenticate_user(user.email, PASSWORD, db)
    await db.refresh(user)
    assert user.failed_login_attempts == 0
    assert user.login_locked_until is None


async def test_unknown_address_fails_identically(db):
    """No enumeration: an address that was never registered answers the same way."""
    with pytest.raises(HTTPException) as exc:
        await authenticate_user("nobody-here@example.com", PASSWORD, db)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid email or password"


# ── Refresh-token rotation and replay ────────────────────────────────


async def test_refresh_rotates_the_token(db):
    user = await _user(db)
    first = await create_refresh_token(user.id, db)

    _, second = await refresh_access_token(first, db)
    assert second != first

    rows = (await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    )).scalars().all()
    assert len(rows) == 1, "the redeemed token must not survive rotation"


async def test_replaying_a_used_token_revokes_the_whole_family(db):
    """The detection half of rotation.

    Rotation alone cannot tell the thief from the victim — whoever refreshes
    second just gets a 401 and the other keeps a working session. Killing every
    session for that user on any replay is what turns a stolen token into a
    forced re-login instead of a quiet persistent foothold.
    """
    user = await _user(db)
    stolen = await create_refresh_token(user.id, db)
    # A second, unrelated session for the same user — a phone, say.
    await create_refresh_token(user.id, db)

    await refresh_access_token(stolen, db)  # legitimate rotation

    with pytest.raises(HTTPException) as exc:
        await refresh_access_token(stolen, db)  # the replay
    assert exc.value.status_code == 401

    rows = (await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    )).scalars().all()
    assert rows == [], "every session for this user should be gone"


async def test_an_expired_refresh_token_is_rejected_and_deleted(db):
    user = await _user(db)
    token = await create_refresh_token(user.id, db)

    row = (await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    )).scalar_one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await refresh_access_token(token, db)
    assert exc.value.status_code == 401

    remaining = (await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    )).scalars().all()
    assert remaining == []


async def test_garbage_is_not_a_refresh_token(db):
    with pytest.raises(HTTPException) as exc:
        await refresh_access_token("not-a-jwt-at-all", db)
    assert exc.value.status_code == 401


async def test_revoking_all_tokens_ends_every_session(db):
    """What a password change relies on."""
    user = await _user(db)
    await create_refresh_token(user.id, db)
    await create_refresh_token(user.id, db)

    await revoke_all_refresh_tokens(user.id, db)

    rows = (await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    )).scalars().all()
    assert rows == []


async def test_one_users_revocation_does_not_touch_another(db):
    a = await _user(db)
    b = await _user(db)
    await create_refresh_token(a.id, db)
    b_token = await create_refresh_token(b.id, db)

    await revoke_all_refresh_tokens(a.id, db)

    still_there = (await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == b.id)
    )).scalars().all()
    assert len(still_there) == 1
    # And it still works.
    await refresh_access_token(b_token, db)
