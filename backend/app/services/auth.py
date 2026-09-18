import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, Response, status
from jwt import PyJWTError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import RefreshToken, User, VerificationToken
from app.schemas.auth import RegisterRequest

logger = logging.getLogger("acadvo.auth")

PURPOSE_PASSWORD_RESET = "password_reset"
PURPOSE_EMAIL_VERIFY = "email_verify"


_ACCESS_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
_REFRESH_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Write the auth cookie pair.

    Lives here rather than in the auth router because every path that mints a
    new session — login, register, refresh, password change — must set cookies
    with identical flags. One copy means one place for `httponly`/`secure`/
    `samesite` to be right.

    The refresh cookie is scoped to `/auth` so it is only ever sent to the
    endpoints that redeem it, instead of riding along on every API request.
    """
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=_ACCESS_MAX_AGE,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=_REFRESH_MAX_AGE,
        path="/auth",
    )


def clear_auth_cookies(response: Response) -> None:
    # `path` must match what set_auth_cookies used, or the browser keeps the
    # cookie and "logout" silently does nothing.
    response.delete_cookie(
        "access_token",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )
    response.delete_cookie(
        "refresh_token",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/auth",
    )


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


# A valid bcrypt hash used to spend the same time verifying a non-existent user as
# a real one, so login response timing doesn't reveal which emails are registered.
_DUMMY_HASH = bcrypt.hashpw(b"timing-equalizer", bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def _hash_token(token: str) -> str:
    """Refresh tokens are stored hashed so a DB leak doesn't yield usable tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


async def create_refresh_token(user_id: uuid.UUID, db: AsyncSession) -> str:
    # Opportunistic cleanup so the table doesn't accumulate dead tokens
    await db.execute(
        delete(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.expires_at < datetime.now(timezone.utc),
        )
    )
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "exp": expire, "type": "refresh", "jti": str(uuid.uuid4())}
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    db_token = RefreshToken(user_id=user_id, token=_hash_token(token), expires_at=expire)
    db.add(db_token)
    await db.commit()

    return token


# The terms version recorded against a new account when the client does not name
# one. Bump it in step with `LAST_UPDATED` in frontend/src/legal/config.js when
# the terms change materially — that is what makes "which version did they
# accept" answerable later.
TERMS_VERSION = "2026-08-23"


async def register_user(data: RegisterRequest, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        university=data.university,
        program=data.program,
        # Stamped server-side. A client-supplied timestamp would be worth less
        # than no record at all, since the whole point is evidence.
        terms_accepted_at=datetime.now(timezone.utc),
        terms_version=data.terms_version or TERMS_VERSION,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# Per-account login throttle. Deliberately a short, escalating delay rather than
# a hard lock: a hard lock lets anyone deny a victim access just by guessing
# wrong a few times, while a backoff still cuts an online guessing attack from
# thousands of attempts per hour down to a handful.
LOGIN_ATTEMPTS_BEFORE_THROTTLE = 5
LOGIN_LOCKOUT_BASE_SECONDS = 30
LOGIN_LOCKOUT_MAX_SECONDS = 15 * 60


def _lockout_for(attempts: int) -> timedelta:
    over = max(0, attempts - LOGIN_ATTEMPTS_BEFORE_THROTTLE)
    seconds = min(LOGIN_LOCKOUT_BASE_SECONDS * (2 ** over), LOGIN_LOCKOUT_MAX_SECONDS)
    return timedelta(seconds=seconds)


async def authenticate_user(email: str, password: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    locked_until = user.login_locked_until if user else None
    if locked_until is not None and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    is_locked = locked_until is not None and locked_until > now

    # Always run a bcrypt verification (against a dummy hash if the user doesn't
    # exist, or if the account is throttled) so an attacker can't tell registered
    # emails — or locked accounts — apart by response timing.
    password_ok = verify_password(
        password, user.hashed_password if user and not is_locked else _DUMMY_HASH
    )

    if user is not None and is_locked:
        # Same 401 as a wrong password: revealing "this account is locked"
        # confirms the address is registered and tells an attacker their guesses
        # are landing.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user is None or not password_ok:
        if user is not None:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= LOGIN_ATTEMPTS_BEFORE_THROTTLE:
                user.login_locked_until = now + _lockout_for(user.failed_login_attempts)
                logger.warning(
                    "login throttled after repeated failures",
                    extra={
                        "user_id": str(user.id),
                        "failed_attempts": user.failed_login_attempts,
                    },
                )
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.failed_login_attempts or user.login_locked_until:
        user.failed_login_attempts = 0
        user.login_locked_until = None
        await db.commit()
    return user


async def refresh_access_token(refresh_token: str, db: AsyncSession) -> tuple[str, str]:
    # Look up the token in the database (stored hashed)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token == _hash_token(refresh_token)))
    db_token = result.scalar_one_or_none()

    if db_token is None:
        # The row is gone, but the token may still be a well-formed JWT we
        # issued — which means it was already redeemed and then presented a
        # second time. Rotation alone cannot tell the thief from the victim
        # (whoever refreshes second just gets a 401), so on any replay we
        # revoke the whole family and force a fresh login. This is the
        # detection half of refresh-token rotation; without it, a stolen token
        # buys an attacker a session that quietly survives.
        await _revoke_family_on_replay(refresh_token, db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if db_token.expires_at < datetime.now(timezone.utc):
        await db.delete(db_token)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    # Verify the JWT is valid and is actually a refresh token
    try:
        payload = jwt.decode(
            refresh_token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        if payload.get("type") != "refresh":
            raise PyJWTError("wrong token type")
        user_id = uuid.UUID(payload["sub"])
    except (PyJWTError, KeyError, ValueError):
        await db.delete(db_token)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Delete the old refresh token
    await db.delete(db_token)
    await db.commit()

    # Create new token pair
    new_access = create_access_token(user_id)
    new_refresh = await create_refresh_token(user_id, db)

    return new_access, new_refresh


async def _revoke_family_on_replay(refresh_token: str, db: AsyncSession) -> None:
    """Revoke every session for the user a replayed refresh token belonged to.

    Only acts when the token verifies as one we actually issued — a random or
    expired string is just an invalid token, not evidence of theft, and must not
    let anyone log other users out.
    """
    try:
        payload = jwt.decode(
            refresh_token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except PyJWTError:
        return
    if payload.get("type") != "refresh":
        return
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        return

    logger.warning(
        "refresh token replay detected; revoking all sessions for user",
        extra={"user_id": str(user_id)},
    )
    await revoke_all_refresh_tokens(user_id, db)


async def revoke_refresh_token(token: str, db: AsyncSession) -> None:
    result = await db.execute(select(RefreshToken).where(RefreshToken.token == _hash_token(token)))
    db_token = result.scalar_one_or_none()
    if db_token is not None:
        await db.delete(db_token)
        await db.commit()


async def revoke_all_refresh_tokens(user_id: uuid.UUID, db: AsyncSession) -> None:
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
    await db.commit()


# ── Single-use verification tokens (password reset, email verification) ──────

async def create_verification_token(
    user_id: uuid.UUID, purpose: str, expire_minutes: int, db: AsyncSession
) -> str:
    """Create a single-use token, invalidating any prior unused tokens of the
    same purpose for this user. Returns the raw token (only its hash is stored)."""
    await db.execute(
        delete(VerificationToken).where(
            VerificationToken.user_id == user_id,
            VerificationToken.purpose == purpose,
            VerificationToken.used_at.is_(None),
        )
    )
    raw = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    db.add(
        VerificationToken(
            user_id=user_id,
            token_hash=_hash_token(raw),
            purpose=purpose,
            expires_at=expires,
        )
    )
    await db.commit()
    return raw


async def consume_verification_token(
    raw_token: str, purpose: str, db: AsyncSession
) -> User | None:
    """Validate and single-use-consume a token. Returns the user on success, else None."""
    result = await db.execute(
        select(VerificationToken).where(
            VerificationToken.token_hash == _hash_token(raw_token),
            VerificationToken.purpose == purpose,
        )
    )
    token = result.scalar_one_or_none()
    if token is None or token.used_at is not None:
        return None

    expires = token.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        return None

    token.used_at = datetime.now(timezone.utc)
    user_result = await db.execute(select(User).where(User.id == token.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        return None
    await db.commit()
    return user
