import uuid

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status
from jwt import PyJWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User


async def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if access_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(
            access_token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            # Reject a token that omits its expiry or subject outright, rather
            # than treating a missing claim as "no constraint".
            options={"require": ["exp", "sub"]},
        )
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# Methods that only read. The verification gate below ignores them so an
# unverified user can still load the app and be told what to do, rather than
# facing a wall of errors with no explanation.
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

# Names the whole class of gated features rather than one of them: this same
# detail is raised for document parsing and course recommendations, so telling a
# user mid-onboarding to verify "to use the AI advisor" describes a feature they
# were not touching. "Settings" is also unreachable during onboarding, so the
# resend instruction stays generic and each screen offers the action in place.
EMAIL_UNVERIFIED_DETAIL = (
    "Verify your email address to use Acadvo's AI features. "
    "Check your inbox, or use the resend link in the app."
)


async def require_verified_email(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    """Block AI requests from accounts with an unverified email address.

    Attached per-router in main.py (and per-endpoint for the AI routes that sit
    inside CRUD routers), so a newly added AI endpoint inherits the gate instead
    of being forgotten — it fails closed.

    Without this, `email_verified` was recorded and never read: anyone could
    register with an address they do not control and get a fully functional
    account, including the AI features that cost real money per call.

    Reads are deliberately still allowed, so the app can load and explain
    itself instead of throwing unexplained errors. The flag is re-read from the
    database on every request (``get_current_user`` already loads the row), so
    verifying takes effect immediately rather than waiting for the access token
    to expire.
    """
    if request.method in _SAFE_METHODS:
        return current_user
    if not current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=EMAIL_UNVERIFIED_DETAIL,
        )
    return current_user
