import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import RefreshToken, User, VerificationToken
from app.schemas.auth import RegisterRequest

PURPOSE_PASSWORD_RESET = "password_reset"
PURPOSE_EMAIL_VERIFY = "email_verify"


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
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(email: str, password: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    # Always run a bcrypt verification (against a dummy hash if the user doesn't
    # exist) so an attacker can't tell registered emails apart by response timing.
    password_ok = verify_password(password, user.hashed_password if user else _DUMMY_HASH)
    if user is None or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return user


async def refresh_access_token(refresh_token: str, db: AsyncSession) -> tuple[str, str]:
    # Look up the token in the database (stored hashed)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token == _hash_token(refresh_token)))
    db_token = result.scalar_one_or_none()

    if db_token is None:
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
        payload = jwt.decode(refresh_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise JWTError("wrong token type")
        user_id = uuid.UUID(payload["sub"])
    except JWTError:
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
