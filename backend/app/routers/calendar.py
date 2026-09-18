from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.limiter import CALENDAR_FEED_LIMIT, limiter
from app.services import calendar as calendar_service

router = APIRouter()


@router.get("/feed/{token}.ics")
# The only route in the API that is both unauthenticated and expensive: every
# hit costs a token lookup plus a full render of the account's events, with no
# session to throttle behind. Keyed on the IP (see CALENDAR_FEED_LIMIT) and set
# high enough that a real subscriber polling on its own schedule never notices.
@limiter.limit(CALENDAR_FEED_LIMIT)
async def calendar_feed(
    request: Request, token: str, db: AsyncSession = Depends(get_db)
):
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
