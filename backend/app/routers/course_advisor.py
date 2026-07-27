import logging
import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.limiter import limiter
from app.models.user import User
from app.schemas.course_recommendation import (
    CourseRecommendationResponse,
    CourseSearchResponse,
    CourseSearchResult,
    RecommendationRequest,
)
from app.services import course_recommendation as rec_service
from app.services.semester_plan import generate_semester_plan, generate_semester_plan_stream, apply_semester_plan

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/search", response_model=CourseSearchResponse)
@limiter.limit("60/hour")
async def search_courses(
    request: Request,
    q: str = Query(..., min_length=2),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results = await rec_service.search_courses(q, current_user.id, db)
    return CourseSearchResponse(
        results=[CourseSearchResult(**r) for r in results],
        query=q,
    )


@router.get("/recommendations", response_model=list[CourseRecommendationResponse])
async def list_recommendations(
    semester: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await rec_service.list_recommendations(current_user.id, db, semester)


@router.post("/recommendations", response_model=list[CourseRecommendationResponse])
@limiter.limit("20/hour")
async def generate_recommendations(
    request: Request,
    body: RecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await rec_service.generate_recommendations(
            current_user.id, body.semester, body.goal, body.requirement_bucket, db
        )
    except Exception:
        logger.exception("Recommendation generation error")
        raise HTTPException(status_code=422, detail="Failed to generate recommendations. Please try again.")


@router.post("/recommendations/{rec_id}/accept", response_model=CourseRecommendationResponse)
async def accept_recommendation(
    rec_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rec = await rec_service.accept_recommendation(rec_id, current_user.id, db)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec


@router.post("/recommendations/{rec_id}/dismiss", response_model=CourseRecommendationResponse)
async def dismiss_recommendation(
    rec_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rec = await rec_service.dismiss_recommendation(rec_id, current_user.id, db)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec


# ── AI Semester Plan ─────────────────────────────────────────────


@router.post("/generate-plan")
@limiter.limit("10/hour")
async def generate_plan(
    request: Request,
    body: dict[str, Any] = Body(default={}),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a full AI-powered semester-by-semester course plan."""
    skip_summers = body.get("skip_summers", True)
    skip_winters = body.get("skip_winters", False)
    try:
        return await generate_semester_plan(current_user.id, db, skip_summers=skip_summers, skip_winters=skip_winters)
    except Exception:
        logger.exception("Semester plan generation error")
        raise HTTPException(status_code=422, detail="Failed to generate plan. Please try again.")


@router.post("/generate-plan/stream")
@limiter.limit("10/hour")
async def generate_plan_stream(
    request: Request,
    body: dict[str, Any] = Body(default={}),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream an AI-generated semester plan via SSE (one semester at a time)."""
    skip_summers = body.get("skip_summers", True)
    skip_winters = body.get("skip_winters", False)
    return StreamingResponse(
        generate_semester_plan_stream(current_user.id, db, skip_summers=skip_summers, skip_winters=skip_winters),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/apply-plan")
async def apply_plan(
    semesters: list[dict[str, Any]] = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Apply the AI-generated plan — adds new planned courses."""
    return await apply_semester_plan(current_user.id, semesters, db)
