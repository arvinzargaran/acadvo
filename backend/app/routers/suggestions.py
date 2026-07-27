import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
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
async def update_suggestion(
    suggestion_id: uuid.UUID,
    data: SuggestionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await suggestion_service.update_suggestion(suggestion_id, user.id, data.accepted, db)
