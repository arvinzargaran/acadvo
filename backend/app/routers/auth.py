from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.limiter import limiter
from app.models.user import User
from app.schemas.auth import (
    DeleteAccountRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.services.auth import (
    PURPOSE_EMAIL_VERIFY,
    PURPOSE_PASSWORD_RESET,
    authenticate_user,
    clear_auth_cookies,
    consume_verification_token,
    create_access_token,
    create_refresh_token,
    create_verification_token,
    hash_password,
    refresh_access_token,
    revoke_all_refresh_tokens,
    revoke_refresh_token,
    register_user,
    set_auth_cookies,
)
from app.services.email import send_email

router = APIRouter()


async def _send_verification_email(user: User, db: AsyncSession) -> None:
    token = await create_verification_token(
        user.id, PURPOSE_EMAIL_VERIFY, settings.EMAIL_VERIFY_TOKEN_EXPIRE_MINUTES, db
    )
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    await send_email(
        user.email,
        "Verify your Acadvo email",
        f"Hi {user.full_name},\n\nConfirm your email address to finish setting up your "
        f"Acadvo account:\n\n{link}\n\nThis link expires in "
        f"{settings.EMAIL_VERIFY_TOKEN_EXPIRE_MINUTES // 60} hours. If you didn't create "
        f"an account, you can ignore this email.",
    )


async def _send_password_reset_email(user: User, db: AsyncSession) -> None:
    token = await create_verification_token(
        user.id, PURPOSE_PASSWORD_RESET, settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES, db
    )
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    await send_email(
        user.email,
        "Reset your Acadvo password",
        f"Hi {user.full_name},\n\nWe received a request to reset your password. Use this "
        f"link to choose a new one:\n\n{link}\n\nThis link expires in "
        f"{settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes. If you didn't request "
        f"this, you can safely ignore this email — your password won't change.",
    )

# Cookie helpers live in services.auth so every session-minting path (here plus
# the password-change endpoint in routers/users.py) writes identical flags.
_set_auth_cookies = set_auth_cookies
_clear_auth_cookies = clear_auth_cookies


@router.post("/register", status_code=200)
@limiter.limit("10/hour")
async def register(
    request: Request,
    response: Response,
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await register_user(data, db)
    await _send_verification_email(user, db)
    access_token = create_access_token(user.id)
    refresh_token = await create_refresh_token(user.id, db)
    _set_auth_cookies(response, access_token, refresh_token)
    return {"detail": "ok"}


@router.post("/login", status_code=200)
@limiter.limit("20/hour")
async def login(
    request: Request,
    response: Response,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(data.email, data.password, db)
    access_token = create_access_token(user.id)
    refresh_token = await create_refresh_token(user.id, db)
    _set_auth_cookies(response, access_token, refresh_token)
    return {"detail": "ok"}


@router.post("/refresh", status_code=200)
@limiter.limit("120/hour")
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    access_token, new_refresh = await refresh_access_token(refresh_token, db)
    _set_auth_cookies(response, access_token, new_refresh)
    return {"detail": "ok"}


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    # Deliberately no get_current_user: once the 30-minute access token expires
    # the user could not reach this endpoint, so their 7-day refresh token would
    # never be revoked server-side. Presenting the refresh cookie is enough to
    # revoke that one token, and there is nothing to abuse — the worst an
    # attacker can do with a token they already hold is log it out.
    if refresh_token:
        await revoke_refresh_token(refresh_token, db)
    _clear_auth_cookies(response)
    return {"detail": "Logged out"}


# ── Password reset ───────────────────────────────────────────────────

@router.post("/forgot-password", status_code=200)
@limiter.limit("5/hour")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if user is not None:
        await _send_password_reset_email(user, db)
    # Always the same response — don't reveal whether an account exists.
    return {"detail": "If an account exists for that email, a reset link has been sent."}


@router.post("/reset-password", status_code=200)
@limiter.limit("10/hour")
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await consume_verification_token(data.token, PURPOSE_PASSWORD_RESET, db)
    if user is None:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")
    user.hashed_password = hash_password(data.new_password)
    await db.commit()
    # Reset invalidates all sessions — anyone holding old tokens is logged out.
    await revoke_all_refresh_tokens(user.id, db)
    return {"detail": "Password updated. You can now sign in with your new password."}


# ── Email verification ───────────────────────────────────────────────

@router.post("/verify-email", status_code=200)
@limiter.limit("20/hour")
async def verify_email(
    request: Request,
    data: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await consume_verification_token(data.token, PURPOSE_EMAIL_VERIFY, db)
    if user is None:
        raise HTTPException(status_code=400, detail="This verification link is invalid or has expired.")
    user.email_verified = True
    await db.commit()
    return {"detail": "Email verified."}


@router.post("/resend-verification", status_code=200)
@limiter.limit("5/hour")
async def resend_verification(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.email_verified:
        return {"detail": "Your email is already verified."}
    await _send_verification_email(current_user, db)
    return {"detail": "Verification email sent."}
