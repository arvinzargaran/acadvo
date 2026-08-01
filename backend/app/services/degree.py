import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.grading_scales import build_grade_map, get_scale, map_percent_to_grade
from app.data.program_config import get_major_gpa_gates
from app.models.degree import Assessment, AssessmentCategory, Course, CourseStatus, Credential, DegreeRequirement
from app.models.user import User
from app.schemas.degree import (
    AssessmentCreate,
    AssessmentUpdate,
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
# Constraint buckets express a rule over other buckets' credits (e.g. "42 credits
# must be at the 3000-level") rather than adding new required credits. They overlap
# Major/electives, so they must be shown as progress but EXCLUDED from the total.
_CONSTRAINT_BUCKET_KEYWORDS = {"upper year", "3000-level", "or higher"}


def _is_total_bucket(name: str) -> bool:
    lower = name.lower()
    return any(kw in lower for kw in _TOTAL_BUCKET_KEYWORDS)


def _is_meta_bucket(name: str) -> bool:
    lower = name.lower()
    return any(kw in lower for kw in _META_BUCKET_KEYWORDS)


def _is_constraint_bucket(name: str) -> bool:
    lower = name.lower()
    return any(kw in lower for kw in _CONSTRAINT_BUCKET_KEYWORDS)


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
        # Constraint buckets (e.g. "Upper Year Requirement") overlap other buckets'
        # credits, so they show progress but must NOT inflate the required total.
        if not _is_constraint_bucket(req.bucket_name):
            total_required += credits_required
        total_completed += credits_completed

    # Use degree total override if available, otherwise sum of bucket requirements
    display_total = degree_total_override if degree_total_override is not None else total_required
    # Always use course-based counting — sum ALL completed courses regardless of bucket
    display_completed = total_all_completed

    overall_percentage = (
        (display_completed / display_total * 100.0) if display_total > 0 else 0.0
    )

    # GPA — delegate to the scale-aware calculator so the summary matches
    # /degree/gpa and uses the student's correct university grading scale.
    gpa_data = await calculate_gpa(user_id, db)
    cumulative_gpa = gpa_data["cumulative_gpa"]
    semester_gpa_list = [
        {"term": t["term"], "gpa": t["gpa"], "credits": t["credits"]}
        for t in gpa_data["term_gpas"]
    ]

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

    # 7. Subject-subset (major) GPAs — only for programs that actually define a
    #    gate (e.g. York's 4.50 EECS-major GPA). Universities without a configured
    #    gate return no major GPAs, so we don't apply York's rule to everyone.
    major_gpas = [
        await calculate_major_gpa(user_id, db, faculty_prefix=g["scope"], gate=g["min"])
        for g in get_major_gpa_gates(university)
    ]

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
        "major_gpas": major_gpas,
    }


async def calculate_major_gpa(
    user_id: uuid.UUID,
    db: AsyncSession,
    faculty_prefix: str = "EECS",
    gate: float = 4.50,
) -> dict:
    """Calculate the major/subject-subset GPA over completed graded courses whose
    course_code contains the given faculty prefix (case-insensitive; handles both
    'LE/EECS 2030' and 'EECS 2030'), using the SAME university-specific grading
    scale as calculate_gpa. Returns scope, gpa, credits and whether it meets the
    program gate (e.g. York's 4.50 EECS-major GPA gate)."""
    # 1. Fetch user's university and resolve the grading scale
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    university = user.university if user else None
    scale, _ = get_scale(university)
    grade_map = build_grade_map(scale)

    # 2. Fetch completed courses
    courses_result = await db.execute(
        select(Course).where(
            Course.user_id == user_id,
            Course.status == CourseStatus.completed,
        )
    )
    courses = list(courses_result.scalars().all())

    # 3. Filter to the subject subset and compute the weighted GPA
    prefix = faculty_prefix.strip().upper()
    weighted_sum = 0.0
    total_credits = 0.0
    for course in courses:
        if not course.grade:
            continue
        if prefix not in (course.course_code or "").upper():
            continue
        grade_upper = course.grade.strip().upper()
        if grade_upper not in grade_map:
            logger.warning(
                "Unrecognized grade '%s' for course %s — skipping", course.grade, course.course_code
            )
            continue
        credits = float(course.credit_value)
        weighted_sum += grade_map[grade_upper] * credits
        total_credits += credits

    gpa = round(weighted_sum / total_credits, 2) if total_credits > 0 else None
    return {
        "scope": faculty_prefix,
        "gpa": gpa,
        "credits": total_credits,
        "gate": gate,
        "meets_gate": gpa is not None and gpa >= gate,
    }


# ── GPA Goal Projection ─────────────────────────────────────────────

async def project_gpa_goal(
    user_id: uuid.UUID, db: AsyncSession, target: float, remaining_credits: float
) -> dict:
    """Reverse-project the average GPA needed on the remaining credits to reach a
    target cumulative GPA.

        needed_average = (target*(completed+remaining) - cumulative*completed)
                         / remaining

    where ``completed`` and ``cumulative`` come from :func:`calculate_gpa` (a
    student with no graded courses yet simply needs to average ``target``). The
    raw requirement is clamped to >= 0 for display; ``already_met`` flags a raw
    value <= 0 (target already secured) and ``achievable`` flags whether it fits
    under the university ``scale_max``. Guards divide-by-zero on remaining <= 0.
    """
    if remaining_credits <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="remaining_credits must be greater than zero.",
        )

    gpa_data = await calculate_gpa(user_id, db)
    completed = gpa_data["total_credits_completed"]
    cumulative = gpa_data["cumulative_gpa"] or 0.0
    scale_max = gpa_data["scale_max"]

    needed = (target * (completed + remaining_credits) - cumulative * completed) / remaining_credits

    return {
        "target": target,
        "remaining_credits": remaining_credits,
        "current_cumulative_gpa": gpa_data["cumulative_gpa"],
        "total_credits_completed": completed,
        "needed_average": round(max(needed, 0.0), 2),
        "achievable": needed <= scale_max + 1e-9,
        "already_met": needed <= 0,
        "scale_max": scale_max,
    }


async def project_major_gpa_goal(
    user_id: uuid.UUID,
    db: AsyncSession,
    remaining_credits: float,
    faculty_prefix: str = "EECS",
    gate: float = 4.50,
) -> dict:
    """Reverse-project the average GPA needed on the next ``remaining_credits`` of
    subject-subset (major) courses to clear a program gate (e.g. York's 4.50
    EECS-major gate). Same math as :func:`project_gpa_goal` with the target fixed
    to ``gate`` and the completed side from :func:`calculate_major_gpa`.

    ``already_met`` is True when the student ALREADY meets the gate (or the raw
    requirement is <= 0). Guards divide-by-zero on remaining <= 0.
    """
    if remaining_credits <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="remaining_credits must be greater than zero.",
        )

    major = await calculate_major_gpa(user_id, db, faculty_prefix=faculty_prefix, gate=gate)
    # calculate_major_gpa uses the same scale; pull scale_max from the cumulative calc.
    gpa_data = await calculate_gpa(user_id, db)
    scale_max = gpa_data["scale_max"]

    completed = major["credits"]
    current = major["gpa"] or 0.0

    needed = (gate * (completed + remaining_credits) - current * completed) / remaining_credits

    return {
        "scope": major["scope"],
        "gate": gate,
        "remaining_credits": remaining_credits,
        "current_major_gpa": major["gpa"],
        "major_credits_completed": completed,
        "needed_average": round(max(needed, 0.0), 2),
        "achievable": needed <= scale_max + 1e-9,
        "already_met": major["meets_gate"] or needed <= 0,
        "meets_gate": major["meets_gate"],
        "scale_max": scale_max,
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


async def get_assessment(
    assessment_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> Assessment:
    """Fetch an assessment, verifying it belongs to a course owned by the user."""
    result = await db.execute(
        select(Assessment)
        .join(Course, Assessment.course_id == Course.id)
        .where(Assessment.id == assessment_id, Course.user_id == user_id)
    )
    assessment = result.scalar_one_or_none()
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    return assessment


async def update_assessment(
    assessment_id: uuid.UUID, user_id: uuid.UUID, data: AssessmentUpdate, db: AsyncSession
) -> Assessment:
    assessment = await get_assessment(assessment_id, user_id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(assessment, field, value)
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)
    return assessment


async def delete_assessment(
    assessment_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> None:
    assessment = await get_assessment(assessment_id, user_id, db)
    await db.delete(assessment)
    await db.commit()


async def project_course_grade(
    course_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession, target: float | None = None
) -> dict:
    """Project a course's final grade from its logged assessment scores.

    Units: each assessment's ``weight`` is a percent of the final grade and its
    ``score`` is a percent (0-100) earned on that assessment. An assessment is
    "graded" once it has a non-null score.

    Definitions (all robust against a total weight that is <100 or >100, e.g. a
    partially-parsed syllabus):
      - earned_points  = Σ weight_i * score_i / 100        (final-grade points)
      - current standing = earned_points / graded_weight * 100  (average on graded work)
      - projected final = current standing extrapolated across the remaining
        (ungraded) weight — i.e. we ASSUME the student maintains their current
        average on what's left. Normalised over total_weight this reduces to the
        current standing, but is computed against total_weight so it stays correct
        when the parsed weights don't sum to 100.
      - if ``target`` (desired final %) is given, the average needed on the
        remaining weight is: (target/100 * total_weight - earned_points) /
        remaining_weight * 100, flagged impossible (>100) or already-secured (<=0).
    """
    await get_course(course_id, user_id, db)
    result = await db.execute(select(Assessment).where(Assessment.course_id == course_id))
    assessments = list(result.scalars().all())

    total_weight = sum(float(a.weight) for a in assessments)
    graded = [a for a in assessments if a.score is not None]
    graded_weight = sum(float(a.weight) for a in graded)
    remaining_weight = max(total_weight - graded_weight, 0.0)
    earned_points = sum(float(a.weight) * float(a.score) / 100.0 for a in graded)

    # Resolve the student's grading scale for letter/GPA mapping.
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    university = user.university if user else None
    scale, using_fallback = get_scale(university)
    scale_max = scale["max_points"]
    scale_name = (
        f"{university} {scale['scale_type']}-point scale"
        if not using_fallback
        else "Standard 4.0 scale"
    )

    current_weighted_pct: float | None = None
    projected_final_pct: float | None = None
    projected_letter: str | None = None
    projected_gpa_points: float | None = None

    if graded_weight > 0:
        current_weighted_pct = round(earned_points / graded_weight * 100.0, 2)
        # Assume current standing is maintained on the remaining weight.
        projected_points = earned_points + remaining_weight * (current_weighted_pct / 100.0)
        projected_final_pct = round(
            projected_points / total_weight * 100.0, 2
        ) if total_weight > 0 else current_weighted_pct
        letter, points = map_percent_to_grade(scale, projected_final_pct)
        projected_letter = letter
        projected_gpa_points = points

    out: dict = {
        "graded_weight": round(graded_weight, 2),
        "total_weight": round(total_weight, 2),
        "remaining_weight": round(remaining_weight, 2),
        "current_weighted_pct": current_weighted_pct,
        "projected_final_pct": projected_final_pct,
        "projected_letter": projected_letter,
        "projected_gpa_points": projected_gpa_points,
        "scale_name": scale_name,
        "scale_max": scale_max,
    }

    if target is not None:
        out["target_final_pct"] = target
        # Points still needed = target share of the whole course minus what's earned.
        needed_points = target / 100.0 * total_weight - earned_points
        if remaining_weight <= 0:
            # Nothing left to grade — achievable only if already at/above target.
            secured = earned_points >= target / 100.0 * total_weight - 1e-9
            out["score_needed_on_remaining"] = None
            out["target_already_secured"] = secured
            out["target_achievable"] = secured
        else:
            needed_avg = needed_points / remaining_weight * 100.0
            already_secured = needed_avg <= 0
            achievable = needed_avg <= 100.0 + 1e-9
            out["score_needed_on_remaining"] = round(max(needed_avg, 0.0), 2)
            out["target_already_secured"] = already_secured
            out["target_achievable"] = achievable

    return out


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
    """Parse a syllabus document via the AI client and save extracted assessments."""
    import base64
    import json
    from datetime import datetime as dt, timezone

    from app.ai.client import get_groq_client
    from app.config import settings
    from app.models.career import TimelineEvent, TimelineCategory
    from app.services.document_parser import (
        SPREADSHEET_MIME_TYPES,
        _pdf_to_text,
        _spreadsheet_to_text,
    )

    # Verify course ownership
    course = await get_course(course_id, user_id, db)

    client = get_groq_client()

    prompt = (
        "You are an expert academic coordinator. Extract all graded assessments from this document "
        "(syllabus, course schedule, exam schedule, or similar). "
        "Return a JSON list of objects with keys: "
        "'title' (string), 'due_date' (ISO format string like '2026-04-15' or null if not specified), "
        "'weight' (percentage as a float, e.g. 25.0 for 25%, or 0 if not specified), "
        "and 'category' (one of: 'exam', 'assignment', 'quiz', 'other'). "
        "Return ONLY valid JSON — no markdown fences, no extra text."
    )

    if mime_type == "application/pdf":
        content_text = _pdf_to_text(file_bytes)
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": f"{prompt}\n\nDocument content:\n\n{content_text}"}],
            max_tokens=4096,
        )
    elif mime_type in SPREADSHEET_MIME_TYPES:
        content_text = _spreadsheet_to_text(file_bytes, mime_type)
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": f"{prompt}\n\nDocument content:\n\n{content_text}"}],
            max_tokens=4096,
        )
    else:
        b64 = base64.b64encode(file_bytes).decode()
        response = client.chat.completions.create(
            model=settings.GROQ_VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
                ],
            }],
            max_tokens=4096,
        )

    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    parsed = json.loads(text)
    if isinstance(parsed, dict) and "assessments" in parsed:
        parsed = parsed["assessments"]
    if not isinstance(parsed, list):
        parsed = []

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
