import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.limiter import CRUD_WRITE_LIMIT, limiter, user_or_ip_key
from app.models.user import User
from app.schemas.suggestion import SuggestionResponse, SuggestionUpdate
from app.services import suggestion as suggestion_service

router = APIRouter()


@router.get("", response_model=list[SuggestionResponse])
async def list_pending_suggestions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await suggestion_service.list_pending_suggestions(user.id, db)


@router.put("/{suggestion_id}", response_model=SuggestionResponse)
@limiter.limit(CRUD_WRITE_LIMIT, key_func=user_or_ip_key)
async def update_suggestion(
    request: Request,
    suggestion_id: uuid.UUID,
    data: SuggestionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await suggestion_service.update_suggestion(suggestion_id, user.id, data.accepted, db)
