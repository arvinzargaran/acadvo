from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.limiter import limiter
from app.models.user import User
from app.schemas.auth import DeleteAccountRequest
from app.schemas.password import Password
from app.schemas.user import UserResponse, UserUpdate
from app.services import calendar as calendar_service
from app.services import user as user_service
from app.services.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    revoke_all_refresh_tokens,
    set_auth_cookies,
    verify_password,
)
from app.services.career import get_readiness_score
from app.services.schedule import get_all_user_events


class PasswordChange(BaseModel):
    current_password: str
    new_password: Password

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/me/readiness")
async def get_readiness(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_readiness_score(current_user.id, db)


@router.get("/me/schedule", response_model=list[dict[str, Any]])
async def get_schedule(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_all_user_events(current_user.id, db)


@router.get("/me/calendar-feed")
async def get_calendar_feed(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    token = await calendar_service.get_or_create_feed_token(current_user, db)
    return {"feed_url": calendar_service.feed_url_for_token(token)}


@router.post("/me/calendar-feed/regenerate")
async def regenerate_calendar_feed(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    token = await calendar_service.regenerate_feed_token(current_user, db)
    return {"feed_url": calendar_service.feed_url_for_token(token)}


@router.put("/me", response_model=UserResponse)
@limiter.limit("30/hour")
async def update_me(
    request: Request,
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await user_service.update_user(current_user, data, db)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/hour")
async def change_password(
    request: Request,
    data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    current_user.hashed_password = hash_password(data.new_password)
    await db.commit()

    # Changing a password is how someone reacts to a suspected compromise, so it
    # has to actually evict the intruder: drop every refresh token, then mint a
    # fresh pair for the device that made the change. Other sessions can no
    # longer refresh and fall off within the access token's 30-minute lifetime.
    await revoke_all_refresh_tokens(current_user.id, db)
    access_token = create_access_token(current_user.id)
    refresh_token = await create_refresh_token(current_user.id, db)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    set_auth_cookies(response, access_token, refresh_token)
    return response


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/hour")
async def delete_me(
    request: Request,
    data: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Re-authenticate: deletion is irreversible, so a stolen/forgotten open
    # session should not be enough to wipe the account.
    if not verify_password(data.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Password is incorrect.")
    await db.delete(current_user)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
