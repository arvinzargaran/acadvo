import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import get_groq_client
from app.config import settings
from app.models.course_recommendation import CourseRecommendation
from app.models.degree import Course, DegreeRequirement, CourseStatus
from app.models.user import User
from app.models.career import CareerTarget
from app.services.catalog import get_catalog
from app.services.degree import get_degree_summary
from app.services.document_parser import normalize_course_code
from app.services.eligibility import (
    evaluate_entry,
    format_allowed_courses,
    get_completed_codes,
    gpa_by_scope_for_catalog,
)


async def list_recommendations(
    user_id: uuid.UUID, db: AsyncSession, semester: str | None = None
) -> list[CourseRecommendation]:
    q = select(CourseRecommendation).where(
        CourseRecommendation.user_id == user_id
    ).order_by(CourseRecommendation.created_at.desc())
    if semester:
        q = q.where(CourseRecommendation.semester == semester)
    result = await db.execute(q)
    return list(result.scalars().all())


async def accept_recommendation(
    rec_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> CourseRecommendation | None:
    result = await db.execute(
        select(CourseRecommendation).where(
            CourseRecommendation.id == rec_id,
            CourseRecommendation.user_id == user_id,
        )
    )
    rec = result.scalar_one_or_none()
    if not rec:
        return None
    rec.accepted = True

    # Find matching requirement bucket
    bucket_id = None
    if rec.requirement_bucket:
        bucket_result = await db.execute(
            select(DegreeRequirement).where(
                DegreeRequirement.user_id == user_id,
                DegreeRequirement.bucket_name == rec.requirement_bucket,
            )
        )
        bucket = bucket_result.scalar_one_or_none()
        if bucket:
            bucket_id = bucket.id

    # Add course to plan
    course = Course(
        user_id=user_id,
        course_code=rec.course_code,
        course_name=rec.course_name,
        credit_value=rec.credits,
        status=CourseStatus.planned,
        term=rec.semester,
        requirement_bucket_id=bucket_id,
    )
    db.add(course)
    await db.commit()
    await db.refresh(rec)
    return rec


async def dismiss_recommendation(
    rec_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> CourseRecommendation | None:
    result = await db.execute(
        select(CourseRecommendation).where(
            CourseRecommendation.id == rec_id,
            CourseRecommendation.user_id == user_id,
        )
    )
    rec = result.scalar_one_or_none()
    if not rec:
        return None
    rec.dismissed = True
    await db.commit()
    await db.refresh(rec)
    return rec


async def _build_user_context(user_id: uuid.UUID, db: AsyncSession) -> dict:
    """Gather full user context for AI recommendations."""
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()

    summary = await get_degree_summary(user_id, db)

    courses_result = await db.execute(
        select(Course).where(Course.user_id == user_id)
    )
    existing_courses = courses_result.scalars().all()
    existing_codes = {c.course_code for c in existing_courses}

    targets_result = await db.execute(
        select(CareerTarget).where(CareerTarget.user_id == user_id)
    )
    targets = targets_result.scalars().all()

    return {
        "university": user.university or "York University",
        "program": user.program or "Computer Science",
        "career_target": user.career_target or "",
        "graduation_year": user.expected_graduation_year,
        "degree_summary": summary,
        "existing_course_codes": list(existing_codes),
        "career_targets": [
            {"company": t.company_name, "role": t.role_type}
            for t in targets
        ],
    }


async def search_courses(
    query: str, user_id: uuid.UUID, db: AsyncSession
) -> list[dict]:
    """Search the university's real catalog for courses matching ``query``.

    The catalog is passed to the LLM as the ONLY allowed set, and every returned
    code is validated against it afterwards (fabricated codes are dropped, and the
    name/credits are overwritten from the authoritative catalog entry)."""
    ctx = await _build_user_context(user_id, db)

    catalog = await get_catalog(ctx["university"], db, user_id)
    existing_norm = {normalize_course_code(c) for c in ctx["existing_course_codes"]}
    allowed_str = format_allowed_courses(catalog)

    client = get_groq_client()

    prompt = f"""You are an academic advisor at {ctx['university']}. From the ALLOWED COURSES list below, pick the courses that best match this query: "{query}"

ALLOWED COURSES (choose ONLY from this list — use these EXACT codes, names and credits; do NOT invent courses):
{allowed_str}

For each matching course provide:
- course_code (must be copied exactly from the list)
- course_name (copied exactly from the list)
- credits (numeric, copied from the list)
- description (1-2 sentences)

Return results as a JSON array. Return ONLY valid JSON, no markdown fences.
If no courses match, return an empty array [].
Find up to 8 matching courses."""

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        raw_results = json.loads(text)
    except json.JSONDecodeError:
        raw_results = []

    # Validate every code against the catalog; drop fabrications and overwrite
    # name/credits from the authoritative entry.
    gpa_by_scope = await gpa_by_scope_for_catalog(catalog, user_id, db)
    completed_codes = await get_completed_codes(user_id, db)

    results = []
    for r in raw_results:
        code = normalize_course_code(r.get("course_code", ""))
        if code not in catalog:
            continue
        entry = catalog[code]
        blocked_reason = evaluate_entry(entry, completed_codes, gpa_by_scope)
        results.append(
            {
                **r,
                "course_code": code,
                "course_name": entry["course_name"],
                "credits": entry["credits"],
                "in_plan": code in existing_norm,
                "requirement_bucket": r.get("requirement_bucket"),
                "eligible": blocked_reason is None,
                "blocked_reason": blocked_reason,
            }
        )

    return results


async def generate_recommendations(
    user_id: uuid.UUID,
    semester: str,
    goal: str,
    requirement_bucket: str | None,
    db: AsyncSession,
) -> list[CourseRecommendation]:
    """Generate AI course recommendations and persist them."""
    ctx = await _build_user_context(user_id, db)

    catalog = await get_catalog(ctx["university"], db, user_id)
    existing_norm = {normalize_course_code(c) for c in ctx["existing_course_codes"]}
    allowed_str = format_allowed_courses(catalog, exclude=existing_norm)

    buckets_info = "\n".join(
        f"- {b['bucket_name']}: {b['credits_completed']}/{b['credits_required']} credits completed ({b['credits_remaining']} remaining)"
        for b in ctx["degree_summary"]["buckets"]
        if b["credits_remaining"] > 0
    )

    existing_list = ", ".join(sorted(ctx["existing_course_codes"])) or "none"
    targets_info = ", ".join(
        f"{t['company']} ({t['role']})" for t in ctx["career_targets"]
    ) or "none specified"

    bucket_filter = ""
    if requirement_bucket:
        bucket_filter = f"\nFocus specifically on courses that satisfy the '{requirement_bucket}' requirement bucket."

    client = get_groq_client()

    prompt = f"""You are a university academic advisor. Recommend 4-6 courses for a {ctx['program']} student at {ctx['university']} to take in {semester}.

STUDENT PROFILE:
- University: {ctx['university']}
- Program: {ctx['program']}
- Career target: {ctx['career_target']}
- Target companies/roles: {targets_info}
- Expected graduation: {ctx['graduation_year']}

DEGREE GAPS (requirement buckets with remaining credits):
{buckets_info or "No gaps identified"}

COURSES ALREADY IN PLAN (do NOT recommend these):
{existing_list}

GOAL: {goal}
{bucket_filter}

ALLOWED COURSES (you MUST choose ONLY from this list — use these EXACT codes, names and credits; do NOT invent or recall courses from memory):
{allowed_str}

INSTRUCTIONS:
- Choose ONLY from the ALLOWED COURSES list above. Never output a course code that is not in that list.
- Recommend courses that serve double duty where possible — courses that satisfy a degree requirement AND build skills relevant to the career target.
- Prioritize courses that close the largest requirement gaps.
- Flag any prerequisites the student may not have met yet (shown as "prereqs:" in the list).
- Be specific about why each course is relevant.

Return a JSON array of objects with these exact keys:
- course_code (string, copied EXACTLY from the ALLOWED COURSES list)
- course_name (string, copied from the list)
- credits (number, copied from the list)
- requirement_bucket (string or null — which degree bucket it satisfies)
- reasoning (string — why this course is recommended)
- career_relevance (string — how it connects to career goals)
- prerequisite_notes (string — any prerequisites to be aware of)
- priority (string — "high", "medium", or "low")

Return ONLY valid JSON, no markdown fences, no extra text."""

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
    )
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        recommendations_data = json.loads(text)
    except json.JSONDecodeError:
        recommendations_data = []

    # ── Server-side validation (never trust the model, even grounded) ──
    # 1. Normalize every code; DROP any that isn't in the real catalog.
    # 2. Overwrite name/credits from the authoritative catalog entry.
    # 3. Compute eligibility (prereqs + GPA gate) and FLAG blocked courses with a
    #    blocked_reason folded into prerequisite_notes (prefer flagging over drop
    #    so the student sees WHY a course is out of reach).
    gpa_by_scope = await gpa_by_scope_for_catalog(catalog, user_id, db)
    completed_codes = await get_completed_codes(user_id, db)

    saved = []
    seen: set[str] = set()
    for rec_data in recommendations_data:
        code = normalize_course_code(rec_data.get("course_code", ""))
        if not code or code in existing_norm or code in seen:
            continue
        entry = catalog.get(code)
        if entry is None:
            # Fabricated / hallucinated code — drop it.
            continue
        seen.add(code)

        blocked_reason = evaluate_entry(entry, completed_codes, gpa_by_scope)
        prereq_notes = rec_data.get("prerequisite_notes") or ""
        if blocked_reason:
            prefix = f"⚠ BLOCKED — {blocked_reason}."
            prereq_notes = f"{prefix} {prereq_notes}".strip() if prereq_notes else prefix

        rec = CourseRecommendation(
            user_id=user_id,
            semester=semester,
            course_code=code,
            course_name=entry["course_name"],
            credits=entry["credits"],
            requirement_bucket=rec_data.get("requirement_bucket"),
            reasoning=rec_data.get("reasoning"),
            career_relevance=rec_data.get("career_relevance"),
            prerequisite_notes=prereq_notes or None,
            priority=rec_data.get("priority", "medium"),
        )
        db.add(rec)
        saved.append(rec)

    await db.commit()
    for rec in saved:
        await db.refresh(rec)

    return saved
