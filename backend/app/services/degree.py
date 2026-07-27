import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.grading_scales import build_grade_map, get_scale
from app.models.degree import Assessment, AssessmentCategory, Course, CourseStatus, Credential, DegreeRequirement
from app.models.user import User
from app.schemas.degree import (
    AssessmentCreate,
    CourseCreate,
    CourseUpdate,
    CredentialCreate,
    CredentialUpdate,
    DegreeRequirementCreate,
    DegreeRequirementUpdate,
)

logger = logging.getLogger(__name__)


# ── Degree Requirements ──────────────────────────────────────────────

async def list_requirements(user_id: uuid.UUID, db: AsyncSession) -> list[DegreeRequirement]:
    result = await db.execute(
        select(DegreeRequirement).where(DegreeRequirement.user_id == user_id)
    )
    return list(result.scalars().all())


async def create_requirement(
    user_id: uuid.UUID, data: DegreeRequirementCreate, db: AsyncSession
) -> DegreeRequirement:
    req = DegreeRequirement(user_id=user_id, **data.model_dump())
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return req


async def get_requirement(
    requirement_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> DegreeRequirement:
    result = await db.execute(
        select(DegreeRequirement).where(
            DegreeRequirement.id == requirement_id,
            DegreeRequirement.user_id == user_id,
        )
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    return req


async def update_requirement(
    requirement_id: uuid.UUID,
    user_id: uuid.UUID,
    data: DegreeRequirementUpdate,
    db: AsyncSession,
) -> DegreeRequirement:
    req = await get_requirement(requirement_id, user_id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(req, field, value)
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return req


# ── Courses ──────────────────────────────────────────────────────────

async def list_courses(user_id: uuid.UUID, db: AsyncSession) -> list[Course]:
    result = await db.execute(select(Course).where(Course.user_id == user_id))
    return list(result.scalars().all())


async def _assert_owns_refs(
    user_id: uuid.UUID,
    requirement_bucket_id: uuid.UUID | None,
    credential_id: uuid.UUID | None,
    db: AsyncSession,
) -> None:
    """Reject foreign requirement-bucket / credential references so a user can't
    link a course to another user's records (cross-tenant reference)."""
    if requirement_bucket_id is not None:
        r = await db.execute(
            select(DegreeRequirement.id).where(
                DegreeRequirement.id == requirement_bucket_id,
                DegreeRequirement.user_id == user_id,
            )
        )
        if r.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement bucket not found")
    if credential_id is not None:
        c = await db.execute(
            select(Credential.id).where(
                Credential.id == credential_id,
                Credential.user_id == user_id,
            )
        )
        if c.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")


async def create_course(user_id: uuid.UUID, data: CourseCreate, db: AsyncSession) -> Course:
    await _assert_owns_refs(user_id, data.requirement_bucket_id, data.credential_id, db)
    course = Course(user_id=user_id, **data.model_dump())
    db.add(course)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.error("Failed to create course %s: %s", data.course_code, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to save course '{data.course_code}'. Please check the values and try again.",
        )
    await db.refresh(course)
    return course


async def get_course(course_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> Course:
    result = await db.execute(
        select(Course).where(Course.id == course_id, Course.user_id == user_id)
    )
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


async def update_course(
    course_id: uuid.UUID, user_id: uuid.UUID, data: CourseUpdate, db: AsyncSession
) -> Course:
    course = await get_course(course_id, user_id, db)
    updates = data.model_dump(exclude_unset=True)
    await _assert_owns_refs(
        user_id,
        updates.get("requirement_bucket_id"),
        updates.get("credential_id"),
        db,
    )
    for field, value in updates.items():
        setattr(course, field, value)
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


async def delete_course(course_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> None:
    course = await get_course(course_id, user_id, db)
    await db.delete(course)
    await db.commit()


# ── Credentials ──────────────────────────────────────────────────────

async def list_credentials(user_id: uuid.UUID, db: AsyncSession) -> list[Credential]:
    result = await db.execute(select(Credential).where(Credential.user_id == user_id))
    return list(result.scalars().all())


async def create_credential(
    user_id: uuid.UUID, data: CredentialCreate, db: AsyncSession
) -> Credential:
    credential = Credential(user_id=user_id, **data.model_dump())
    db.add(credential)
    await db.commit()
    await db.refresh(credential)
    return credential


async def get_credential(
    credential_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> Credential:
    result = await db.execute(
        select(Credential).where(
            Credential.id == credential_id, Credential.user_id == user_id
        )
    )
    credential = result.scalar_one_or_none()
    if credential is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")
    return credential


async def update_credential(
    credential_id: uuid.UUID,
    user_id: uuid.UUID,
    data: CredentialUpdate,
    db: AsyncSession,
) -> Credential:
    credential = await get_credential(credential_id, user_id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(credential, field, value)
    db.add(credential)
    await db.commit()
    await db.refresh(credential)
    return credential


async def delete_credential(
    credential_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> None:
    credential = await get_credential(credential_id, user_id, db)
    await db.delete(credential)
    await db.commit()


# ── Degree Summary ───────────────────────────────────────────────────

_TOTAL_BUCKET_KEYWORDS = {"degree total", "total credits", "program total"}
_META_BUCKET_KEYWORDS = {"gpa", "average"}


def _is_total_bucket(name: str) -> bool:
    lower = name.lower()
    return any(kw in lower for kw in _TOTAL_BUCKET_KEYWORDS)


def _is_meta_bucket(name: str) -> bool:
    lower = name.lower()
    return any(kw in lower for kw in _META_BUCKET_KEYWORDS)


async def get_degree_summary(user_id: uuid.UUID, db: AsyncSession) -> dict:
    requirements = await list_requirements(user_id, db)
    # Only fetch completed courses — that's all the summary and GPA need
    courses_result = await db.execute(
        select(Course).where(Course.user_id == user_id, Course.status == CourseStatus.completed)
    )
    courses = list(courses_result.scalars().all())

    # Index completed credits by requirement bucket
    completed_by_bucket: dict[uuid.UUID, float] = {}
    total_all_completed = 0.0
    for course in courses:
        if course.status == CourseStatus.completed:
            total_all_completed += float(course.credit_value)
            if course.requirement_bucket_id is not None:
                completed_by_bucket[course.requirement_bucket_id] = (
                    completed_by_bucket.get(course.requirement_bucket_id, 0.0)
                    + float(course.credit_value)
                )

    buckets = []
    total_required = 0.0
    total_completed = 0.0
    degree_total_override: float | None = None

    for req in requirements:
        credits_required = float(req.credits_required)
        credits_completed = completed_by_bucket.get(req.id, 0.0)

        # Detect the "Degree Total Credits" meta-bucket
        if _is_total_bucket(req.bucket_name):
            degree_total_override = credits_required
            continue

        # Skip GPA / meta-buckets with 0 credits
        if _is_meta_bucket(req.bucket_name) and credits_required == 0:
            continue

        credits_remaining = max(credits_required - credits_completed, 0.0)
        percentage = (credits_completed / credits_required * 100.0) if credits_required > 0 else 0.0
        at_risk = credits_remaining > 0 and percentage < 50.0

        buckets.append(
            {
                "bucket_name": req.bucket_name,
                "credits_required": credits_required,
                "credits_completed": credits_completed,
                "credits_remaining": credits_remaining,
                "percentage": round(percentage, 2),
                "at_risk": at_risk,
            }
        )
        total_required += credits_required
        total_completed += credits_completed

    # Use degree total override if available, otherwise sum of bucket requirements
    display_total = degree_total_override if degree_total_override is not None else total_required
    # Always use course-based counting — sum ALL completed courses regardless of bucket
    display_completed = total_all_completed

    overall_percentage = (
        (display_completed / display_total * 100.0) if display_total > 0 else 0.0
    )

    # GPA calculation
    gpa_points = {
        "A+": 4.0, "A": 4.0, "A-": 3.7,
        "B+": 3.3, "B": 3.0, "B-": 2.7,
        "C+": 2.3, "C": 2.0, "C-": 1.7,
        "D+": 1.3, "D": 1.0, "D-": 0.7,
        "F": 0.0, "E": 0.0,
    }
    weighted_sum = 0.0
    gpa_credits = 0.0
    semester_gpas = {}
    for course in courses:
        if course.status == CourseStatus.completed and course.grade:
            grade_upper = course.grade.strip().upper()
            if grade_upper in gpa_points:
                weight = float(course.credit_value)
                points = gpa_points[grade_upper] * weight
                weighted_sum += points
                gpa_credits += weight
                term = course.term or "Unknown"
                if term not in semester_gpas:
                    semester_gpas[term] = {"points": 0.0, "credits": 0.0}
                semester_gpas[term]["points"] += points
                semester_gpas[term]["credits"] += weight

    cumulative_gpa = round(weighted_sum / gpa_credits, 2) if gpa_credits > 0 else None
    semester_gpa_list = []
    for term, data in sorted(semester_gpas.items()):
        if data["credits"] > 0:
            semester_gpa_list.append({
                "term": term,
                "gpa": round(data["points"] / data["credits"], 2),
                "credits": data["credits"],
            })

    return {
        "buckets": buckets,
        "total_credits_required": display_total,
        "total_credits_completed": display_completed,
        "overall_percentage": round(overall_percentage, 2),
        "cumulative_gpa": cumulative_gpa,
        "semester_gpas": semester_gpa_list,
    }


# ── GPA Calculator ──────────────────────────────────────────────────

async def calculate_gpa(user_id: uuid.UUID, db: AsyncSession) -> dict:
    """Calculate GPA using the student's university-specific grading scale."""
    # 1. Fetch user's university
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    university = user.university if user else None

    # 2. Look up grading scale
    scale, using_fallback = get_scale(university)
    grade_map = build_grade_map(scale)
    scale_max = scale["max_points"]
    scale_name = f"{university} {scale['scale_type']}-point scale" if not using_fallback else "Standard 4.0 scale"

    # 3. Fetch completed courses with grades
    courses_result = await db.execute(
        select(Course).where(
            Course.user_id == user_id,
            Course.status == CourseStatus.completed,
        )
    )
    courses = list(courses_result.scalars().all())

    # 4. Calculate
    weighted_sum = 0.0
    total_credits = 0.0
    graded_count = 0
    term_data: dict[str, dict] = {}

    for course in courses:
        if not course.grade:
            continue
        grade_upper = course.grade.strip().upper()
        if grade_upper not in grade_map:
            logger.warning("Unrecognized grade '%s' for course %s — skipping", course.grade, course.course_code)
            continue

        points = grade_map[grade_upper]
        credits = float(course.credit_value)
        weighted_sum += points * credits
        total_credits += credits
        graded_count += 1

        term = course.term or "Unknown"
        if term not in term_data:
            term_data[term] = {"points": 0.0, "credits": 0.0, "count": 0}
        term_data[term]["points"] += points * credits
        term_data[term]["credits"] += credits
        term_data[term]["count"] += 1

    cumulative_gpa = round(weighted_sum / total_credits, 2) if total_credits > 0 else None

    # 5. Build term GPAs — sort chronologically by (year, season order)
    _SEASON_ORDER = {"winter": 0, "spring": 1, "summer": 2, "fall": 3}

    def _term_sort_key(t: str) -> tuple:
        parts = t.lower().split()
        season = _SEASON_ORDER.get(parts[0], 99) if parts else 99
        year = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        return (year, season)

    term_gpas = []
    for term in sorted(term_data.keys(), key=_term_sort_key):
        d = term_data[term]
        if d["credits"] > 0:
            term_gpas.append({
                "term": term,
                "gpa": round(d["points"] / d["credits"], 2),
                "credits": d["credits"],
                "course_count": d["count"],
            })

    # 6. Highest / lowest term
    highest_term = None
    lowest_term = None
    if term_gpas:
        highest_term = max(term_gpas, key=lambda t: t["gpa"])
        lowest_term = min(term_gpas, key=lambda t: t["gpa"])

    return {
        "cumulative_gpa": cumulative_gpa,
        "term_gpas": term_gpas,
        "total_credits_completed": total_credits,
        "graded_course_count": graded_count,
        "highest_term": highest_term,
        "lowest_term": lowest_term,
        "scale_max": scale_max,
        "scale_name": scale_name,
        "using_fallback": using_fallback,
    }


# ── Assessments ────────────────────────────────────────────────────

async def list_assessments(
    course_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> list[Assessment]:
    # Verify course belongs to user
    await get_course(course_id, user_id, db)
    result = await db.execute(
        select(Assessment).where(Assessment.course_id == course_id)
    )
    return list(result.scalars().all())


async def create_assessment(
    course_id: uuid.UUID, user_id: uuid.UUID, data: AssessmentCreate, db: AsyncSession
) -> Assessment:
    await get_course(course_id, user_id, db)
    assessment = Assessment(course_id=course_id, **data.model_dump())
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)
    return assessment


async def delete_assessments_for_course(
    course_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> None:
    await get_course(course_id, user_id, db)
    result = await db.execute(
        select(Assessment).where(Assessment.course_id == course_id)
    )
    for a in result.scalars().all():
        await db.delete(a)
    await db.commit()


async def parse_and_save_syllabus(
    course_id: uuid.UUID, user_id: uuid.UUID, file_bytes: bytes, mime_type: str, db: AsyncSession
) -> list[Assessment]:
    """Parse a syllabus document via Gemini and save extracted assessments."""
    import json
    from google.genai import types
    from app.ai.client import get_gemini_client
    from app.config import settings
    from app.models.career import TimelineEvent, TimelineCategory
    from datetime import datetime as dt

    # Verify course ownership
    course = await get_course(course_id, user_id, db)

    client = get_gemini_client()

    prompt = (
        "You are an expert academic coordinator. Extract all graded assessments from this document "
        "(syllabus, course schedule, exam schedule, or similar). "
        "Return a JSON list of objects with keys: "
        "'title' (string), 'due_date' (ISO format string like '2026-04-15' or null if not specified), "
        "'weight' (percentage as a float, e.g. 25.0 for 25%, or 0 if not specified), "
        "and 'category' (one of: 'exam', 'assignment', 'quiz', 'other'). "
        "Return ONLY valid JSON — no markdown fences, no extra text."
    )

    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=[
            prompt,
            types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
        ]
    )

    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    parsed = json.loads(text)
    if isinstance(parsed, dict) and "assessments" in parsed:
        parsed = parsed["assessments"]

    # Build a set of existing assessment titles to avoid duplicates
    existing = await db.execute(
        select(Assessment).where(Assessment.course_id == course_id)
    )
    existing_titles = {a.title.strip().lower() for a in existing.scalars().all()}

    saved = []
    for item in parsed:
        title = item.get("title", "").strip()
        if not title:
            continue
        # Skip duplicates from previous uploads
        if title.lower() in existing_titles:
            continue
        existing_titles.add(title.lower())

        due_date = None
        raw_date = item.get("due_date")
        if raw_date:
            try:
                due_date = dt.fromisoformat(raw_date)
                if due_date.tzinfo is None:
                    due_date = due_date.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                pass

        weight = float(item.get("weight", 0))
        category_str = item.get("category", "other")
        try:
            category = AssessmentCategory(category_str)
        except ValueError:
            category = AssessmentCategory.other

        assessment = Assessment(
            course_id=course_id,
            title=title,
            due_date=due_date,
            weight=weight,
            category=category,
            notes=item.get("notes"),
        )
        db.add(assessment)
        saved.append(assessment)

        # Create a timeline event for assessments with due dates
        if due_date:
            event = TimelineEvent(
                user_id=user_id,
                title=f"{course.course_code}: {title}",
                description=f"Weight: {weight}% — {category.value}",
                event_date=due_date.date() if hasattr(due_date, "date") else due_date,
                category=TimelineCategory.deadline,
                is_hard_deadline=True,
            )
            db.add(event)

    await db.commit()
    for a in saved:
        await db.refresh(a)

    return saved
