import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.suggestion import AISuggestion


async def list_pending_suggestions(
    user_id: uuid.UUID, db: AsyncSession
) -> list[AISuggestion]:
    result = await db.execute(
        select(AISuggestion)
        .where(AISuggestion.user_id == user_id, AISuggestion.accepted.is_(None))
        .order_by(AISuggestion.created_at.desc())
    )
    return list(result.scalars().all())


async def update_suggestion(
    suggestion_id: uuid.UUID, user_id: uuid.UUID, accepted: bool, db: AsyncSession
) -> AISuggestion:
    result = await db.execute(
        select(AISuggestion).where(AISuggestion.id == suggestion_id)
    )
    suggestion = result.scalar_one_or_none()
    if suggestion is None or suggestion.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found")

    suggestion.accepted = accepted
    await db.commit()
    await db.refresh(suggestion)
    return suggestion
