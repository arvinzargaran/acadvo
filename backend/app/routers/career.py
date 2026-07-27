import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.limiter import limiter
from app.models.user import User
from app.schemas.career import (
    CareerTargetCreate,
    CareerTargetResponse,
    CareerTargetUpdate,
    TimelineEventCreate,
    TimelineEventResponse,
)
from app.services import career as career_service

router = APIRouter()


# ── Career Targets ─────────────────────────────────────────────────


@router.get("/targets", response_model=list[CareerTargetResponse])
async def list_career_targets(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await career_service.list_career_targets(user.id, db)


@router.post("/targets", response_model=CareerTargetResponse, status_code=201)
async def create_career_target(
    data: CareerTargetCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await career_service.create_career_target(user.id, data, db)


@router.put("/targets/{target_id}", response_model=CareerTargetResponse)
async def update_career_target(
    target_id: uuid.UUID,
    data: CareerTargetUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await career_service.update_career_target(target_id, user.id, data, db)


@router.delete("/targets/{target_id}", status_code=204)
async def delete_career_target(
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
async def create_timeline_event(
    data: TimelineEventCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await career_service.create_timeline_event(user.id, data, db)


@router.delete("/timeline/{event_id}", status_code=204)
async def delete_timeline_event(
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


@router.post("/review-resume")
@limiter.limit("5/hour")
async def review_resume(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in _RESUME_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. Upload a PDF or image.",
        )

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

    import base64
    import io
    from app.ai.client import get_groq_client
    from app.config import settings

    client = get_groq_client()

    prompt = _RESUME_REVIEW_PROMPT.format(
        university=current_user.university or "Unknown",
        program=current_user.program or "Unknown",
        career_target=current_user.career_target or "Software Engineering",
    )

    try:
        if file.content_type == "application/pdf":
            import pdfplumber
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                resume_text = "\n\n".join(p.extract_text() or "" for p in pdf.pages)
            response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": f"{prompt}\n\nResume text:\n\n{resume_text}"}],
                max_tokens=2048,
            )
        else:
            b64 = base64.b64encode(file_bytes).decode()
            response = client.chat.completions.create(
                model=settings.GROQ_VISION_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{file.content_type};base64,{b64}"}},
                    ],
                }],
                max_tokens=2048,
            )
        text = response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail="AI could not process this file. Try a clearer scan or different format.",
        )

    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    # Record that the user reviewed their resume
    current_user.last_resume_review = datetime.now(timezone.utc)
    db.add(current_user)
    await db.commit()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"summary": text, "overall_score": None}
