import logging
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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
from app.ai.client import AI_PROVIDER_ERRORS
from app.services.catalog import UniversityNotSetError
from app.ai.research_client import is_research_enabled
from app.config import settings
from app.models.requirement_rule import JOB_FAILED, JOB_PENDING, JOB_RUNNING
from app.research import runner as research_runner
from app.research.program_rules import check_requirements_url
from app.research.schema import RuleRejected, validate_requirements_url
from app.services import course_recommendation as rec_service
from app.services.requirement_rules import get_rules, rules_summary
from app.services.semester_plan import PlanGenerationError, generate_semester_plan, generate_semester_plan_stream, apply_semester_plan

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
    except rec_service.NoCoverageError as exc:
        # Same class of problem as NoCatalogError — the server can't satisfy this
        # yet and retrying won't change that — so the same non-retryable 409.
        raise HTTPException(status_code=409, detail=str(exc))
    except UniversityNotSetError as exc:
        # 409 alongside NoCatalogError: the request is fine, the profile is not.
        raise HTTPException(status_code=409, detail=str(exc))
    except rec_service.NoCatalogError as exc:
        # Not a failure to retry: there is no catalog for this university, so
        # retrying produces the same nothing. 409 rather than 422 — the request
        # was fine, the server state can't satisfy it. Caught before the
        # catch-all below, which would otherwise tell the student to "try again".
        raise HTTPException(status_code=409, detail=str(exc))
    except AI_PROVIDER_ERRORS:
        # Re-raised so main.py's handlers can name the real cause.
        raise
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


# ── Program requirement rules (researched once, cached, reused) ──────
#
# The read side of the "AI decides, decision is cached" design. This endpoint is
# also a research trigger: a student opening their planner in an uncovered
# program is exactly the signal that program is worth researching, which is how
# coverage grows from real usage instead of from someone maintaining a list.


def _research_state(job, rule_count: int, enabled: bool) -> tuple[str, str]:
    """Map job + rule state to a (state, message) the UI can render verbatim.

    Every branch says what Acadvo does NOT know, because the alternative — a
    spinner that never resolves, or a blank panel — reads to a student as "this
    course does not count for anything", which is a claim nobody made.
    """
    if rule_count:
        return "ready", f"Acadvo has requirement rules for {rule_count} bucket(s) in your program."
    if not enabled:
        return (
            "unavailable",
            "Acadvo has not worked out your program's requirement rules, and "
            "requirement research is not configured on this server. Course "
            "advice still works; it just will not say which requirement a "
            "course satisfies.",
        )
    if job is None:
        return (
            "needs_url",
            "Acadvo can work out which courses satisfy each of your degree "
            "requirements — it just needs a link to your program's official "
            "requirements page to read. Paste one and it will apply to every "
            "student in your program.",
        )
    if job.status in (JOB_PENDING, JOB_RUNNING):
        return (
            "researching",
            "Acadvo is reading your university's published requirements for your "
            "program. This runs once and then applies to every student in it — "
            "your planner and GPA tracking work normally meanwhile.",
        )
    if job.status == JOB_FAILED:
        return (
            "failed",
            "Acadvo could not read your program's requirements from that page, so "
            "it will not guess which requirement a course satisfies. Try a "
            "different link to your program's official requirements. Everything "
            "else still works.",
        )
    return (
        "empty",
        "Acadvo's research found no requirement rules it could verify for your "
        "program.",
    )


@router.get("/program-rules")
async def program_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """What Acadvo knows about this student's program requirements, and why."""
    university, program = current_user.university, current_user.program
    rules = await get_rules(university, program, db)
    enabled = is_research_enabled()

    if not rules and settings.RESEARCH_USE_SEARCH_GROUNDING:
        # Auto-queue only when the model can FIND the pages itself. Without
        # Search grounding a job with no URL cannot succeed, and enqueueing one
        # would show the student a spinner that resolves to a failure instead of
        # the "paste your requirements page" prompt that would actually help.
        await research_runner.ensure_research(db, university, program)

    job = await research_runner.get_job(db, university, program)
    state, message = _research_state(job, len(rules), enabled)

    return {
        "university": university,
        "program": program,
        "state": state,
        "message": message,
        "research_enabled": enabled,
        "job": None
        if job is None
        else {
            "status": job.status,
            "attempts": job.attempts,
            "requested_at": job.requested_at,
            "finished_at": job.finished_at,
            # Surfaced rather than buried in logs: "we could not read your
            # university's pages" is a legitimate answer a student can act on.
            "last_error": job.last_error,
            "source_urls": list(job.source_urls or []),
        },
        **rules_summary(rules),
    }


class ProgramRulesRequest(BaseModel):
    """The one thing a human supplies in this whole pipeline.

    Finding the requirements page automatically needs a web search, which does
    not fit the free tier's per-request token limit; reading a page you name
    costs no tokens at all. So one student per program links their official
    requirements page, and every student in that program is covered from then
    on — the same bargain as the checklist upload.

    The URL is fetched server-side, so it is validated twice before anything
    opens it: ``validate_requirements_url`` here, and a DNS-resolving check on
    every redirect hop in ``research_client``.
    """

    model_config = ConfigDict(extra="ignore")

    url: str = Field(min_length=8, max_length=2000)


@router.post("/program-rules/research")
@limiter.limit("5/day")
async def research_program_rules_endpoint(
    request: Request,
    body: ProgramRulesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Queue research for this student's program from a requirements page URL."""
    if not is_research_enabled():
        raise HTTPException(
            status_code=503,
            detail="Requirement research is not configured on this server.",
        )
    if not current_user.university or not current_user.program:
        raise HTTPException(
            status_code=422,
            detail="Set your university and program before requesting requirement research.",
        )
    try:
        url = validate_requirements_url(body.url)
        # Whose page it is matters as much as whether it is fetchable. Rules are
        # stored per (university, program) and shared with everyone in that
        # program, and both strings come off this student's own profile — so
        # without this check, claiming another cohort's university and program
        # and linking a lookalike page replaces their requirements with yours.
        # See app/research/program_rules.py for the full policy, including what
        # happens for a university Acadvo has no domain for.
        check_requirements_url(current_user.university, url)
    except RuleRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    job = await research_runner.request_refresh(
        db, current_user.university, current_user.program, urls=[url]
    )
    return {
        "status": job.status,
        "source_urls": list(job.source_urls or []),
        # `request_refresh` can decline to re-queue a program that has already
        # failed its attempt ceiling on these exact URLs. Saying "Queued" then
        # would be a lie the student waits on, so the message follows the job's
        # real status rather than assuming the happy path.
        "message": (
            "Queued. Acadvo will read that page and work out your program's "
            "requirement rules — they will appear here shortly, and will apply to "
            "every student in your program."
            if job.status == JOB_PENDING
            else (
                "Acadvo has already tried that page several times without being "
                "able to read your program's requirements from it, so it will not "
                "try again right now. Link a different official requirements page."
            )
        ),
    }


@router.post("/program-rules/refresh")
@limiter.limit("3/day")
async def refresh_program_rules(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ask for this program's rules to be re-researched.

    Rate-limited hard: this is the one expensive call in the system, and a
    per-program job row means a re-run helps everyone in the program, so nobody
    needs to trigger it often.
    """
    if not is_research_enabled():
        raise HTTPException(
            status_code=503,
            detail="Requirement research is not configured on this server.",
        )
    if not current_user.university or not current_user.program:
        raise HTTPException(
            status_code=422,
            detail="Set your university and program before requesting requirement research.",
        )
    job = await research_runner.request_refresh(
        db, current_user.university, current_user.program
    )
    return {
        "status": job.status if job else "unavailable",
        "message": (
            "Queued. Requirement rules will appear here once the research completes."
            if job and job.status == JOB_PENDING
            else (
                "Acadvo has already tried this program's pages several times "
                "without success, so it will not retry immediately. Link a "
                "different official requirements page instead."
            )
        ),
    }


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
    except AI_PROVIDER_ERRORS:
        # Re-raised so main.py's handlers can name the real cause.
        raise
    except UniversityNotSetError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except PlanGenerationError as exc:
        # Already phrased for the student, and it says which of the two things
        # went wrong (cut short vs. unusable), so it is not flattened.
        logger.warning("Semester plan unusable: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc))
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


class PlannedCourse(BaseModel):
    """One course in a plan the client is asking us to persist.

    This body was previously an untyped `list[dict]`, so whatever the client
    sent went straight into the DB — a string where a number belongs, or a
    `credits` value that does not fit Numeric(4,2), surfaced as an unhandled
    500 and silently corrupted credit totals.
    """

    model_config = ConfigDict(extra="ignore")

    course_code: str = Field(min_length=1, max_length=20)
    course_name: str = Field(default="", max_length=200)
    credits: float = Field(default=3.0, ge=0, le=20)
    reason: str | None = Field(default=None, max_length=2000)


class PlannedSemester(BaseModel):
    model_config = ConfigDict(extra="ignore")

    term: str = Field(min_length=1, max_length=50)
    courses: list[PlannedCourse] = Field(default_factory=list, max_length=20)


@router.post("/apply-plan")
async def apply_plan(
    semesters: list[PlannedSemester] = Body(..., max_length=40),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Apply the AI-generated plan — adds new planned courses."""
    return await apply_semester_plan(
        current_user.id, [s.model_dump() for s in semesters], db
    )
