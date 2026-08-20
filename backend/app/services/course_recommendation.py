import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import acomplete, get_groq_client, completion_text, json_kwargs
from app.config import settings
from app.models.course_recommendation import CourseRecommendation
from app.models.degree import Course, DegreeRequirement, CourseStatus
from app.models.user import User
from app.models.career import CareerTarget
from app.services.catalog import get_catalog, require_university
from app.services.degree import get_degree_summary
from app.services.document_parser import normalize_course_code, subject_of
from app.services.eligibility import (
    evaluate_entry,
    expand_equivalents,
    format_allowed_courses,
    shortlist_for_query,
    shortlist_for_student,
    undergraduate_only,
    get_completed_codes,
    gpa_by_scope_for_catalog,
)
from app.research.runner import ensure_research
from app.services.requirement_rules import EXCLUDED, classify_course, get_rules


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

    # Courses that are genuinely spoken for, and so must not be recommended
    # again. Deliberately NOT every row the student has.
    #
    # Uploading a degree checklist creates a row for every requirement in the
    # program, most of them `not_scheduled` — meaning "required, not yet
    # scheduled". Those are the exact courses an advisor exists to recommend.
    # Treating every row as "already in plan" meant a student who uploaded their
    # checklist excluded their whole program from advice and got nothing back:
    # the more completely they filled in their degree, the less the advisor
    # could say.
    settled_codes = {
        c.course_code
        for c in existing_courses
        if c.status
        in (CourseStatus.completed, CourseStatus.in_progress, CourseStatus.planned)
    }

    targets_result = await db.execute(
        select(CareerTarget).where(CareerTarget.user_id == user_id)
    )
    targets = targets_result.scalars().all()

    return {
        # No fallback university: see UniversityNotSetError. Program keeps a
        # generic default because it only ever shapes prompt wording, never
        # which catalog the advice is drawn from.
        "university": require_university(user),
        "program": user.program or "Computer Science",
        "career_target": user.career_target or "",
        "graduation_year": user.expected_graduation_year,
        "degree_summary": summary,
        "existing_course_codes": list(existing_codes),
        "settled_course_codes": list(settled_codes),
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
    # "In plan" means done / taking / scheduled. A `not_scheduled` checklist row
    # is a requirement the student still has to fit in somewhere, so flagging it
    # as already handled tells them the opposite of the truth.
    settled_norm = {normalize_course_code(c) for c in ctx["settled_course_codes"]}
    # Shortlist, not the whole catalog — see the note above shortlist_for_query.
    # Validation below still runs against the full catalog, so this can only
    # narrow the candidates, never widen what is accepted.
    allowed_str = format_allowed_courses(
        shortlist_for_query(undergraduate_only(catalog), query), ordered=True
    )

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

    response = await acomplete(
        client,
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
        **json_kwargs(),
    )
    text = completion_text(response)

    try:
        raw_results = json.loads(text)
    except json.JSONDecodeError:
        raw_results = []

    # Validate every code against the catalog; drop fabrications and overwrite
    # name/credits from the authoritative entry.
    gpa_by_scope = await gpa_by_scope_for_catalog(catalog, user_id, db)
    completed_codes = await get_completed_codes(user_id, db)
    rules = await get_rules(ctx["university"], ctx["program"], db)

    results = []
    for r in raw_results:
        code = normalize_course_code(r.get("course_code", ""))
        if code not in catalog:
            continue
        entry = catalog[code]
        blocked_reason = evaluate_entry(entry, completed_codes, gpa_by_scope)
        # Same honesty contract as the recommendation path: a search result that
        # says "counts toward X" carries the label and the citation, or it says
        # nothing about counting at all.
        verdict = classify_course(rules, code) if rules else None
        results.append(
            {
                **r,
                "course_code": code,
                "course_name": entry["course_name"],
                "credits": entry["credits"],
                "in_plan": code in settled_norm,
                "requirement_bucket": r.get("requirement_bucket"),
                "eligible": blocked_reason is None,
                "blocked_reason": blocked_reason,
                "bucket_verdict": verdict.as_dict() if verdict is not None else None,
            }
        )

    return results


def _has_allowed_courses(catalog: dict[str, dict], exclude: set[str]) -> bool:
    """True when at least one catalog course is available to recommend.

    Checked against the catalog itself rather than the rendered prompt string,
    so it stays correct if the rendering ever changes.
    """
    return any(code not in exclude for code in catalog)


def _subjects(codes) -> set[str]:
    """Subject prefixes ("EECS", "PSYC") for a set of course codes."""
    return {s for s in (subject_of(c) for c in codes) if s}


def catalog_covers_student(catalog: dict[str, dict], student_codes) -> bool:
    """Does this catalog cover the subject areas this student actually studies?

    A catalog is built one program document at a time, so it is almost never
    university-wide. Ingesting a Computer Science checklist gives York a real
    catalog — of EECS and MATH courses. For a York Psychology student that
    catalog is *present* but useless, and worse than absent: without this check
    they stop getting "no catalog" and start getting recommended EECS courses,
    which is confidently wrong rather than merely unhelpful.

    Coverage is measured against the SEEDED layer only. ``get_catalog`` merges
    the student's own courses in as a fallback, so the merged catalog always
    contains their subjects and would always look "covered" — the question being
    asked here is whether Acadvo has verified data for their area, not whether
    they typed some.

    Two cases pass without assertion:
      * No seeded catalog at all — the student's own uploaded checklist IS the
        catalog, which is the legitimate uncatalogued-university path.
      * A student with no courses yet — no subjects to compare, so coverage is
        unknowable and refusing would be a guess.
    """
    verified = {
        code for code, e in catalog.items() if e.get("source") == "catalog"
    }
    if not verified:
        return True
    student_subjects = _subjects(student_codes)
    if not student_subjects:
        return True
    return bool(student_subjects & _subjects(verified))


class NoCoverageError(RuntimeError):
    """Raised when a catalog exists but covers none of the student's subjects."""

    def __init__(self, university: str, subjects: set[str]):
        self.university = university
        self.subjects = subjects
        listed = ", ".join(sorted(subjects)) or "your program"
        super().__init__(
            f"Acadvo's {university} catalog does not cover {listed} yet, so it "
            "cannot recommend courses for your program without guessing. Your "
            "degree planner, GPA tracking, and everything you have entered by "
            "hand still work."
        )


def _student_subjects(ctx: dict) -> set[str]:
    """Subject prefixes the student's own courses are in ("EECS", "PSYC", ...).

    Used to bias a shortlist toward the part of the catalog their degree is
    actually made of. Empty for a brand-new account, which simply means the
    shortlist falls back to code order.
    """
    subjects = set()
    for code in list(ctx.get("existing_course_codes") or []) + list(ctx.get("settled_course_codes") or []):
        head = str(code or "").split(" ")[0]
        subject = head.split("/")[-1].upper()
        if subject:
            subjects.add(subject)
    return subjects


class NoCatalogError(RuntimeError):
    """Raised when there is nothing the advisor is allowed to recommend from.

    Recommendations are grounded strictly in the university's catalog, and every
    code the model returns that is not in that catalog is dropped. So when the
    allowed list is empty the pipeline cannot produce anything — it would spend a
    model call and hand back an empty array that looks identical to "we thought
    about it and you need nothing."

    That silence is the failure. A student at a university Acadvo has not seeded
    a catalog for is exactly the person who most needs to be told the tool does
    not cover them yet, rather than being shown a blank panel.
    """

    def __init__(self, university: str):
        self.university = university
        super().__init__(
            f"No verified course catalog for {university}. Acadvo can only "
            "recommend courses it can verify, so recommendations are unavailable "
            "until a catalog is loaded for your university. Your degree planner, "
            "GPA tracking, and everything you have entered by hand still work."
        )


async def generate_recommendations(
    user_id: uuid.UUID,
    semester: str,
    goal: str,
    requirement_bucket: str | None,
    db: AsyncSession,
) -> list[CourseRecommendation]:
    """Generate AI course recommendations and persist them.

    Raises ``NoCatalogError`` when the student's university has no catalog to
    recommend from — see that class for why this is loud rather than empty.
    """
    ctx = await _build_user_context(user_id, db)

    # First student in this program? Queue the research that works out its
    # requirement rules. Deliberately before every guard below, because the
    # student who gets NoCatalogError is exactly the one whose program needs
    # looking at. This returns immediately — it enqueues, it does not research —
    # so nothing here waits on a web call, and it never raises.
    await ensure_research(db, ctx["university"], ctx["program"])

    catalog = await get_catalog(ctx["university"], db, user_id)
    # Exclude only courses that are settled — completed, in progress, or already
    # scheduled — plus anything equivalent to them (don't offer EECS 1015 to a
    # student who completed its alternative 1012). Requirements sitting at
    # `not_scheduled` stay in play; recommending them is the whole job.
    settled_norm = expand_equivalents(
        {normalize_course_code(c) for c in ctx["settled_course_codes"]}
    )
    allowed_str = format_allowed_courses(
        shortlist_for_student(
            undergraduate_only(catalog),
            _student_subjects(ctx),
            program=ctx.get("program"),
            exclude=settled_norm,
        ),
        ordered=True,
    )

    # Nothing to choose from: stop before the model call rather than paying for a
    # generation whose every code will be dropped by validation below.
    if not _has_allowed_courses(catalog, settled_norm):
        raise NoCatalogError(ctx["university"])

    # A catalog that covers other people's programs is not a catalog for this
    # student. Checked after the emptiness guard so the clearer "no catalog"
    # message wins when there is genuinely nothing at all.
    student_codes = {normalize_course_code(c) for c in ctx["existing_course_codes"]}
    if not catalog_covers_student(catalog, student_codes):
        raise NoCoverageError(ctx["university"], _subjects(student_codes))

    buckets_info = "\n".join(
        f"- {b['bucket_name']}: {b['credits_completed']}/{b['credits_required']} credits completed ({b['credits_remaining']} remaining)"
        for b in ctx["degree_summary"]["buckets"]
        if b["credits_remaining"] > 0
    )

    # Only the settled ones — listing every checklist row here would tell the
    # model not to recommend the same courses the ALLOWED list just offered it.
    settled_list = ", ".join(sorted(ctx["settled_course_codes"])) or "none"
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

COURSES ALREADY DONE, IN PROGRESS, OR SCHEDULED (do NOT recommend these):
{settled_list}

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

    response = await acomplete(
        client,
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
        **json_kwargs(),
    )
    text = completion_text(response)

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
    # Loaded once for the whole batch: these are cached rows, not a model call.
    # Empty until this program's research lands, in which case every verdict is
    # None and the pipeline behaves exactly as it did before rules existed.
    rules = await get_rules(ctx["university"], ctx["program"], db)

    validated = []
    seen: set[str] = set()
    for rec_data in recommendations_data:
        code = normalize_course_code(rec_data.get("course_code", ""))
        if not code or code in settled_norm or code in seen:
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

        # Correct an obvious bucket mislabel: EECS/MATH courses are never
        # "Foundational Science Lab" credits (that bucket is wet-lab sciences only).
        req_bucket = rec_data.get("requirement_bucket")
        if (
            entry.get("subject_faculty") in {"EECS", "MATH"}
            and req_bucket
            and "lab" in req_bucket.lower()
        ):
            req_bucket = "Major Requirements"

        # ── The bucket claim, checked against the university's own rules ──
        #
        # "This satisfies your General Education requirement" is the single
        # sentence in this product that can be wrong without anyone noticing: the
        # student believes it, plans around it, and finds out at their graduation
        # audit. So the model's claim is not passed through.
        #
        # Three outcomes, in order of how much they matter:
        #   * The rule EXCLUDES this course from the bucket the model named. The
        #     claim is retracted outright — repeating it would be actively
        #     harmful, and the verdict records why so the student sees the
        #     correction rather than a silent edit.
        #   * The rule supports the claim. It is kept, and the verdict carries
        #     the stated/inferred label plus the source URLs.
        #   * No rule covers this course. The claim is left alone and the verdict
        #     is None — an uncovered program is a gap in what Acadvo knows, and
        #     overwriting the model's guess with our own silence helps nobody.
        verdict = classify_course(rules, code, bucket_name=req_bucket) if rules else None
        if verdict is None and rules and req_bucket:
            # The model named a bucket this program does not have. Fall back to
            # asking what the rules say about the course at all.
            verdict = classify_course(rules, code)
        if verdict is not None and verdict.outcome == EXCLUDED and req_bucket:
            req_bucket = None

        rec = CourseRecommendation(
            user_id=user_id,
            semester=semester,
            course_code=code,
            course_name=entry["course_name"],
            credits=entry["credits"],
            requirement_bucket=req_bucket,
            reasoning=rec_data.get("reasoning"),
            career_relevance=rec_data.get("career_relevance"),
            prerequisite_notes=prereq_notes or None,
            priority=rec_data.get("priority", "medium"),
            bucket_verdict=verdict.as_dict() if verdict is not None else None,
        )
        validated.append((blocked_reason is None, rec))

    # Surface courses the student can actually take NOW first; within each group
    # keep the model's high/medium/low ordering.
    _prio_rank = {"high": 0, "medium": 1, "low": 2}
    validated.sort(key=lambda t: (not t[0], _prio_rank.get(t[1].priority, 1)))

    saved = [rec for _, rec in validated]
    for rec in saved:
        db.add(rec)
    await db.commit()
    for rec in saved:
        await db.refresh(rec)

    return saved
