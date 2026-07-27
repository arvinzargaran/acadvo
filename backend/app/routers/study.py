from datetime import date, datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.limiter import limiter
from app.models.study import StudySession
from app.models.user import User
from app.schemas.study import StudySessionCreate, StudySessionResponse, StudyStatsResponse

router = APIRouter()


@router.post("/session", response_model=StudySessionResponse)
@limiter.limit("60/hour")
async def log_study_session(
    request: Request,
    session_in: StudySessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = datetime.now(timezone.utc).date()
    
    new_session = StudySession(
        user_id=current_user.id,
        duration_minutes=session_in.duration_minutes,
        date=today,
    )
    db.add(new_session)

    result = await db.scalars(
        select(StudySession)
        .where(StudySession.user_id == current_user.id)
        .where(StudySession.date == today)
    )
    today_sessions = result.all()
    
    previous_today_minutes = sum(s.duration_minutes for s in today_sessions)
    new_today_minutes = previous_today_minutes + session_in.duration_minutes

    goal = current_user.daily_study_goal_minutes

    if previous_today_minutes < goal and new_today_minutes >= goal:
        last_date = current_user.last_study_date
        
        if last_date == today:
            pass
        elif last_date == today - timedelta(days=1):
            current_user.study_streak += 1
        else:
            current_user.study_streak = 1
            
        if current_user.study_streak > current_user.longest_study_streak:
            current_user.longest_study_streak = current_user.study_streak
            
        current_user.last_study_date = today

    await db.commit()
    await db.refresh(new_session)
    return new_session


@router.get("/stats", response_model=StudyStatsResponse)
async def get_study_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = datetime.now(timezone.utc).date()
    
    result = await db.scalar(
        select(func.coalesce(func.sum(StudySession.duration_minutes), 0))
        .where(StudySession.user_id == current_user.id)
        .where(StudySession.date == today)
    )
    today_minutes = result or 0

    last_date = current_user.last_study_date
    if last_date and last_date < today - timedelta(days=1) and current_user.study_streak > 0:
        current_user.study_streak = 0
        await db.commit()

    week_start = today - timedelta(days=6)
    result = await db.scalars(
        select(StudySession)
        .where(StudySession.user_id == current_user.id)
        .where(StudySession.date >= week_start)
    )
    sessions = result.all()
    
    activity_map = {week_start + timedelta(days=i): 0 for i in range(7)}
    for s in sessions:
        if s.date in activity_map:
            activity_map[s.date] += s.duration_minutes
            
    week_activity = [activity_map[week_start + timedelta(days=i)] for i in range(7)]

    return StudyStatsResponse(
        current_streak=current_user.study_streak,
        longest_streak=current_user.longest_study_streak,
        last_study_date=current_user.last_study_date,
        daily_goal_minutes=current_user.daily_study_goal_minutes,
        today_minutes=today_minutes,
        week_activity=week_activity
    )
