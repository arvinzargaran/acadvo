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
from app.services.degree import get_degree_summary


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
    """Search university courses via Gemini with web search grounding."""
    ctx = await _build_user_context(user_id, db)

    client = get_groq_client()

    prompt = f"""You are an academic advisor. Recommend courses at {ctx['university']} matching: "{query}"

Based on your knowledge of Canadian university curricula, for each matching course provide:
- course_code (e.g. "EECS 3101")
- course_name
- credits (numeric, e.g. 3.0)
- description (1-2 sentences)

Return results as a JSON array. Return ONLY valid JSON, no markdown fences.
If no courses are found, return an empty array [].
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
        results = json.loads(text)
    except json.JSONDecodeError:
        results = []

    # Mark courses already in plan
    for r in results:
        r["in_plan"] = r.get("course_code", "") in ctx["existing_course_codes"]
        # Try to match requirement bucket
        r.setdefault("requirement_bucket", None)

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

INSTRUCTIONS:
- Recommend courses that serve double duty where possible — courses that satisfy a degree requirement AND build skills relevant to the career target.
- Prioritize courses that close the largest requirement gaps.
- Flag any prerequisites the student may not have met yet.
- Be specific about why each course is relevant.
- Recommend real courses with accurate course codes from {ctx['university']}.

Return a JSON array of objects with these exact keys:
- course_code (string, e.g. "EECS 3101")
- course_name (string)
- credits (number, e.g. 3.0)
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

    # Persist recommendations
    saved = []
    for rec_data in recommendations_data:
        code = rec_data.get("course_code", "")
        if not code or code in ctx["existing_course_codes"]:
            continue

        rec = CourseRecommendation(
            user_id=user_id,
            semester=semester,
            course_code=code,
            course_name=rec_data.get("course_name", ""),
            credits=rec_data.get("credits", 3.0),
            requirement_bucket=rec_data.get("requirement_bucket"),
            reasoning=rec_data.get("reasoning"),
            career_relevance=rec_data.get("career_relevance"),
            prerequisite_notes=rec_data.get("prerequisite_notes"),
            priority=rec_data.get("priority", "medium"),
        )
        db.add(rec)
        saved.append(rec)

    await db.commit()
    for rec in saved:
        await db.refresh(rec)

    return saved
