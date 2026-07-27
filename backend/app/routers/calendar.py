from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import calendar as calendar_service

router = APIRouter()


@router.get("/feed/{token}.ics")
async def calendar_feed(token: str, db: AsyncSession = Depends(get_db)):
    """Public .ics feed for calendar apps to subscribe to. Auth is the opaque
    token itself, not a session — calendar clients poll this unattended."""
    user = await calendar_service.get_user_by_feed_token(token, db)
    if user is None:
        raise HTTPException(status_code=404, detail="Feed not found")

    ics = await calendar_service.build_ics_feed(user.id, db)
    return Response(
        content=ics,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'inline; filename="acadvo.ics"',
            "Cache-Control": "private, max-age=1800",
        },
    )
