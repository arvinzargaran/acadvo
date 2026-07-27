from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.services.weekly_summary import generate_weekly_summary

router = APIRouter()


@router.get("/weekly-summary")
async def weekly_summary(
    refresh: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await generate_weekly_summary(user, db, force_refresh=refresh)
