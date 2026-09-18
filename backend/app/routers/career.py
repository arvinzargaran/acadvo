import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_verified_email
from app.limiter import CRUD_WRITE_LIMIT, limiter, user_or_ip_key
from app.models.user import User
from app.schemas.career import (
    CareerTargetCreate,
    CareerTargetResponse,
    CareerTargetUpdate,
    TimelineEventCreate,
    TimelineEventResponse,
)
from app.services import career as career_service
from app.services.uploads import UploadTooComplexError, pdf_to_text, validate_upload

router = APIRouter()


# ── Career Targets ─────────────────────────────────────────────────


@router.get("/targets", response_model=list[CareerTargetResponse])
async def list_career_targets(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await career_service.list_career_targets(user.id, db)


@router.post("/targets", response_model=CareerTargetResponse, status_code=201)
@limiter.limit(CRUD_WRITE_LIMIT, key_func=user_or_ip_key)
async def create_career_target(
    request: Request,
    data: CareerTargetCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await career_service.create_career_target(user.id, data, db)


@router.put("/targets/{target_id}", response_model=CareerTargetResponse)
@limiter.limit(CRUD_WRITE_LIMIT, key_func=user_or_ip_key)
async def update_career_target(
    request: Request,
    target_id: uuid.UUID,
    data: CareerTargetUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await career_service.update_career_target(target_id, user.id, data, db)


@router.delete("/targets/{target_id}", status_code=204)
@limiter.limit(CRUD_WRITE_LIMIT, key_func=user_or_ip_key)
async def delete_career_target(
    request: Request,
    target_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await career_service.delete_career_target(target_id, user.id, db)


# ── Timeline Events ───────────────────────────────────────────────


@router.get("/timeline", response_model=list[TimelineEventResponse])
async def list_timeline_events(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await career_service.list_timeline_events(user.id, db)


@router.post("/timeline", response_model=TimelineEventResponse, status_code=201)
@limiter.limit(CRUD_WRITE_LIMIT, key_func=user_or_ip_key)
async def create_timeline_event(
    request: Request,
    data: TimelineEventCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await career_service.create_timeline_event(user.id, data, db)


@router.delete("/timeline/{event_id}", status_code=204)
@limiter.limit(CRUD_WRITE_LIMIT, key_func=user_or_ip_key)
async def delete_timeline_event(
    request: Request,
    event_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await career_service.delete_timeline_event(event_id, user.id, db)


# ── Resume Review ────────────────────────────────────────────────

_RESUME_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/jpg", "image/webp"}
_MAX_FILE_SIZE = 10 * 1024 * 1024

_RESUME_REVIEW_PROMPT = """You are an expert career advisor and resume reviewer for computer science students.

Analyze this resume/cover letter and provide a structured review. The student's context:
- University: {university}
- Program: {program}
- Career target: {career_target}

Return your review as JSON with this structure:
{{
  "overall_score": <number 1-10>,
  "summary": "<2-3 sentence overall assessment>",
  "strengths": ["<strength 1>", "<strength 2>", ...],
  "improvements": [
    {{"area": "<area>", "issue": "<what's wrong>", "suggestion": "<specific fix>"}},
    ...
  ],
  "missing_sections": ["<section that should be added>", ...],
  "ats_tips": ["<tip for passing ATS systems>", ...],
  "tailored_advice": "<advice specific to their career target>"
}}

Be specific and actionable. Reference actual content from the document."""


# AI-backed and costly: requires a verified email (see main.py).
@router.post("/review-resume", dependencies=[Depends(require_verified_email)])
@limiter.limit("5/hour", key_func=user_or_ip_key)
async def review_resume(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.size is not None and file.size > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum 10MB.",
        )
    file_bytes = await file.read()
    if len(file_bytes) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum 10MB.",
        )

    # Validate against the real bytes, not the client-supplied Content-Type.
    mime_type = validate_upload(file_bytes, file.content_type, _RESUME_MIME_TYPES)

    import base64
    from app.ai.client import (
        json_kwargs,
        AI_PROVIDER_ERRORS,
        acomplete,
        completion_text,
        get_groq_client,
        run_blocking,
        vision_kwargs,
    )
    from app.config import settings

    client = get_groq_client()

    prompt = _RESUME_REVIEW_PROMPT.format(
        university=current_user.university or "Unknown",
        program=current_user.program or "Unknown",
        career_target=current_user.career_target or "Software Engineering",
    )

    try:
        if mime_type == "application/pdf":
            # Bounded page/character extraction, in a worker thread — an
            # unbounded pdfplumber pass on the event loop stalls every request.
            resume_text = await run_blocking(pdf_to_text, file_bytes)
            response = await acomplete(
                client,
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": f"{prompt}\n\nResume text:\n\n{resume_text}"}],
                max_tokens=2048,
                **json_kwargs(),
            )
        else:
            b64 = base64.b64encode(file_bytes).decode()
            response = await acomplete(
                client,
                model=settings.GROQ_VISION_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
                    ],
                }],
                max_tokens=2048,
                **vision_kwargs(),
            )
        text = completion_text(response)
    except UploadTooComplexError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e)
        )
    except AI_PROVIDER_ERRORS:
        # Re-raised so main.py's handlers can name the real cause.
        raise
    except Exception:
        raise HTTPException(
            status_code=422,
            detail="AI could not process this file. Try a clearer scan or different format.",
        )

    # Record that the user reviewed their resume
    current_user.last_resume_review = datetime.now(timezone.utc)
    db.add(current_user)
    await db.commit()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"summary": text, "overall_score": None}
