"""
AI-powered full semester plan generation.

Uses Groq (Llama) with university-scoped prompts to create an intelligent
semester-by-semester course plan from now until graduation.
"""

import json
import logging
import re
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import get_groq_client
from app.config import settings

logger = logging.getLogger(__name__)
from app.models.career import CareerTarget
from app.models.degree import Course, CourseStatus, DegreeRequirement
from app.models.user import User
from app.services.catalog import get_catalog
from app.services.degree import get_degree_summary
from app.services.document_parser import normalize_course_code
from app.services.eligibility import (
    evaluate_entry,
    expand_equivalents,
    format_allowed_courses,
    gpa_by_scope_for_catalog,
    missing_prerequisite_group,
)

MAX_COURSES_PER_SEMESTER = 5

# Maps season name to the month it ENDS (used to determine if a semester is in the past)
_SEASON_END_MONTH = {"winter": 4, "spring": 4, "summer": 8, "fall": 12}
_SEASON_START_MONTH = {"winter": 1, "summer": 5, "fall": 9}


def _current_semester() -> str:
    """Return the current semester name, e.g. 'Winter 2026'."""
    now = date.today()
    month = now.month
    year = now.year
    if month <= 4:
        return f"Winter {year}"
    elif month <= 8:
        return f"Summer {year}"
    else:
        return f"Fall {year}"


def _semester_is_past_or_current(term: str) -> bool:
    """Check if a semester term string is in the past or is the current semester."""
    current = _current_semester()
    try:
        parts = term.strip().split()
        season = parts[0].lower()
        year = int(parts[1])
    except (IndexError, ValueError):
        return False

    try:
        cur_parts = current.split()
        cur_season = cur_parts[0].lower()
        cur_year = int(cur_parts[1])
    except (IndexError, ValueError):
        return False

    if year < cur_year:
        return True
    if year > cur_year:
        return False
    # Same year: compare season order
    season_order = {"winter": 0, "spring": 1, "summer": 2, "fall": 3}
    return season_order.get(season, 0) <= season_order.get(cur_season, 0)


def _build_future_semesters(
    grad_year: int | None,
    skip_summers: bool = False,
    skip_winters: bool = False,
) -> list[str]:
    """Build list of FUTURE semesters (excluding current) from now to graduation."""
    now = date.today()
    current_year = now.year
    current_month = now.month
    end_year = grad_year or current_year + 3

    semesters = []
    for y in range(current_year, end_year + 1):
        for season, month_start in [("Winter", 1), ("Summer", 5), ("Fall", 9)]:
            if y > end_year:
                break
            # Skip if this semester has already started
            if y == current_year and month_start <= current_month:
                continue
            # Apply opt-out preferences
            if skip_summers and season == "Summer":
                continue
            if skip_winters and season == "Winter":
                continue
            semesters.append(f"{season} {y}")

    return semesters


async def _gather_context(
    user_id: uuid.UUID,
    db: AsyncSession,
    skip_summers: bool = False,
    skip_winters: bool = False,
) -> dict:
    """Gather everything the AI needs to build a plan."""
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()

    summary = await get_degree_summary(user_id, db)

    courses_result = await db.execute(select(Course).where(Course.user_id == user_id))
    courses = list(courses_result.scalars().all())

    reqs_result = await db.execute(select(DegreeRequirement).where(DegreeRequirement.user_id == user_id))
    reqs = list(reqs_result.scalars().all())

    targets_result = await db.execute(select(CareerTarget).where(CareerTarget.user_id == user_id))
    targets = list(targets_result.scalars().all())

    completed = [c for c in courses if c.status == CourseStatus.completed]
    in_progress = [c for c in courses if c.status == CourseStatus.in_progress]
    planned = [c for c in courses if c.status == CourseStatus.planned]
    all_codes = {c.course_code for c in courses}

    future_semesters = _build_future_semesters(
        user.expected_graduation_year,
        skip_summers=skip_summers,
        skip_winters=skip_winters,
    )

    # Ground the plan in the real catalog and precompute the student's major GPA
    # for every gate scope (used to keep gated courses blocked in _sanitize_plan).
    university = user.university or "York University"
    catalog = await get_catalog(university, db, user_id)
    gpa_by_scope = await gpa_by_scope_for_catalog(catalog, user_id, db)
    # Equivalence-expanded so a completed course also counts as its alternatives
    # (satisfies prereqs, and lets _sanitize_plan drop the redundant alternative).
    completed_codes = expand_equivalents(
        {normalize_course_code(c.course_code) for c in completed if c.course_code}
    )

    return {
        "user": user,
        "summary": summary,
        "completed": completed,
        "in_progress": in_progress,
        "planned": planned,
        "all_codes": all_codes,
        "requirements": reqs,
        "career_targets": targets,
        "future_semesters": future_semesters,
        "current_semester": _current_semester(),
        "skip_summers": skip_summers,
        "skip_winters": skip_winters,
        "catalog": catalog,
        "gpa_by_scope": gpa_by_scope,
        "completed_codes": completed_codes,
    }


def _build_prompt(ctx: dict) -> str:
    user = ctx["user"]
    summary = ctx["summary"]
    today = date.today().isoformat()
    current_sem = ctx["current_semester"]

    # Format completed courses — normalize short offering terms to be clear
    completed_str = "\n".join(
        f"  - {c.course_code}: {c.course_name} ({c.credit_value} cr, grade: {c.grade or 'N/A'})"
        for c in ctx["completed"]
    ) or "  None"

    in_progress_str = "\n".join(
        f"  - {c.course_code}: {c.course_name} ({c.credit_value} cr)"
        for c in ctx["in_progress"]
    ) or "  None"

    already_planned_str = "\n".join(
        f"  - {c.course_code}: {c.course_name} ({c.credit_value} cr, assigned to: {c.term or 'TBD'})"
        for c in ctx["planned"]
    ) or "  None"

    # Collect all course codes that are already taken, in progress, or planned
    taken_codes = {c.course_code for c in ctx["completed"]} | {c.course_code for c in ctx["in_progress"]}
    all_existing_codes = taken_codes | {c.course_code for c in ctx["planned"]}
    taken_str = ", ".join(sorted(all_existing_codes)) or "none"

    # Format requirement gaps
    buckets_str = "\n".join(
        f"  - {b['bucket_name']}: {b['credits_completed']}/{b['credits_required']} cr done, {b['credits_remaining']} remaining"
        for b in summary["buckets"]
        if b["credits_remaining"] > 0
    ) or "  All requirements met!"

    # Career targets
    targets_str = "\n".join(
        f"  - {t.company_name} ({t.role_type or 'unspecified role'}) — {t.status}"
        for t in ctx["career_targets"]
    ) or "  None specified"

    future_semesters_str = ", ".join(ctx["future_semesters"])

    skip_summers = ctx.get("skip_summers", False)
    skip_winters = ctx.get("skip_winters", False)

    # Build semester exclusion rules for prompt hardening
    semester_exclusion_rules = ""
    if skip_summers:
        semester_exclusion_rules += "\n10. SUMMER SEMESTERS ARE STRICTLY FORBIDDEN. You MUST NOT place any courses in any Summer term (e.g. Summer 2026, Summer 2027). The student has opted out of Summer semesters. Distribute those courses into Fall and Winter terms instead."
    if skip_winters:
        semester_exclusion_rules += f"\n{'11' if skip_summers else '10'}. WINTER SEMESTERS ARE STRICTLY FORBIDDEN. You MUST NOT place any courses in any Winter term (e.g. Winter 2027, Winter 2028). The student has opted out of Winter semesters. Distribute those courses into Fall and Summer terms instead."

    from app.ai.tool_executor import UNIVERSITY_DOMAINS
    domain = UNIVERSITY_DOMAINS.get(user.university, "")

    # Allowed course list from the real catalog, excluding courses already taken /
    # in progress / planned so the model only proposes NEW, real courses.
    exclude_norm = {normalize_course_code(c) for c in all_existing_codes}
    allowed_str = format_allowed_courses(ctx.get("catalog", {}), exclude=exclude_norm)

    return f"""You are an expert academic advisor at {user.university or 'a Canadian university'}.
Your job is to create a semester-by-semester course plan for FUTURE semesters only.

TODAY'S DATE: {today}
CURRENT SEMESTER: {current_sem} (already in progress — do NOT plan for this semester)

CRITICAL RULES — YOU MUST FOLLOW ALL OF THESE:
1. ONLY plan for these FUTURE semesters: {future_semesters_str}
2. Do NOT include any past or current semesters. Do NOT include {current_sem} or any earlier semester.
3. Do NOT recommend any course the student has already completed or is currently taking.
4. EXISTING COURSE CODES — DO NOT INCLUDE ANY OF THESE (already completed, in progress, or planned): {taken_str}
5. Maximum {MAX_COURSES_PER_SEMESTER} courses per semester (typically 4-5, around 12-15 credits). NEVER exceed {MAX_COURSES_PER_SEMESTER}. This is a HARD limit.
6. Choose courses ONLY from the ALLOWED COURSES list below. Use these EXACT codes, names and credits. Do NOT invent course codes or recall courses from memory.
7. Consider PREREQUISITES (shown as "prereqs:" in the list): don't schedule a course before its prerequisites are completed or scheduled in an EARLIER semester of this plan. A course with a "gate:" (GPA gate) requires the student's major GPA to reach that threshold first.
8. Consider CAREER ALIGNMENT: prioritize courses that build skills for the student's career goals.
9. For elective slots, recommend SPECIFIC courses that align with career goals, not just "Elective".{semester_exclusion_rules}

STUDENT PROFILE:
- University: {user.university or 'Unknown'}
- Program: {user.program or 'Computer Science'}
- Career target: {user.career_target or 'Software Engineering'}
- Start year: {user.start_year or 'Unknown'}
- Expected graduation: {user.expected_graduation_year or 'Unknown'}

CAREER TARGETS:
{targets_str}

COURSES ALREADY COMPLETED — DO NOT INCLUDE:
{completed_str}

COURSES IN PROGRESS THIS SEMESTER ({current_sem}) — DO NOT INCLUDE:
{in_progress_str}

COURSES ALREADY PLANNED — DO NOT INCLUDE (student has already scheduled these):
{already_planned_str}

UNFILLED DEGREE REQUIREMENTS:
{buckets_str}

Overall progress: {summary['overall_percentage']}% — {summary['total_credits_completed']}/{summary['total_credits_required']} credits

ALLOWED COURSES (choose ONLY from this list — exact codes/names/credits; "prereqs:" and "gate:" show what must be satisfied first):
{allowed_str}

Return a JSON object with this structure:
{{
  "plan_summary": "<2-3 sentence overview of the plan strategy>",
  "semesters": [
    {{
      "term": "<e.g. Summer 2026 — MUST be one of the future semesters listed above>",
      "courses": [
        {{
          "course_code": "<actual course code>",
          "course_name": "<full course name>",
          "credits": <number>,
          "requirement_bucket": "<which requirement this satisfies or null>",
          "reasoning": "<why this course, this semester>",
          "prerequisites": "<prerequisites, or 'None'>",
          "career_relevance": "<how it helps career goals>"
        }}
      ],
      "semester_notes": "<any notes about this semester — co-op term, heavier/lighter load, etc.>"
    }}
  ],
  "warnings": ["<any concerns — tight timeline, missing prereqs, heavy semesters, etc.>"]
}}

Return ONLY valid JSON. No markdown fences. No extra text.
Be SPECIFIC — use real course codes from {user.university or 'the university'}."""


def _is_skipped_season(term: str, ctx: dict) -> bool:
    """Check if a semester term should be skipped based on user preferences."""
    try:
        season = term.strip().split()[0].lower()
    except (IndexError, AttributeError):
        return False
    if ctx.get("skip_summers") and season == "summer":
        return True
    if ctx.get("skip_winters") and season == "winter":
        return True
    return False


_SEASON_ORDER = {"winter": 0, "spring": 1, "summer": 2, "fall": 3}


def _term_sort_key(term: str) -> tuple[int, int]:
    parts = (term or "").strip().split()
    season = _SEASON_ORDER.get(parts[0].lower(), 99) if parts else 99
    year = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    return (year, season)


def _prepare_course(
    course: dict,
    *,
    catalog: dict,
    all_existing_codes: set,
    already_completed: set,
    placed_codes: set,
    this_codes: list,
) -> tuple[str, dict | None] | None:
    """Canonicalize + validate a single course dict IN PLACE. Returns ``(code, entry)``
    to keep it, or ``None`` to drop it (empty/duplicate/already-completed/fabricated).

    ``entry`` is the authoritative catalog record (``None`` when the catalog is
    unavailable — we then fail OPEN and keep the model's course as-is)."""
    code = normalize_course_code(course.get("course_code", ""))
    if not code or code in placed_codes or code in this_codes or code in already_completed:
        return None
    entry = catalog.get(code)
    if entry is None and catalog:
        # Catalog loaded but this code isn't in it → fabricated; drop it.
        return None
    course["course_code"] = code
    if entry is not None:
        course["course_name"] = entry["course_name"]
        course["credits"] = entry["credits"]
    course["already_in_plan"] = code in all_existing_codes
    return code, entry


def _sanitize_plan(plan: dict, ctx: dict) -> dict:
    """Post-process the AI plan to enforce hard constraints AND validate against
    the real catalog:
      - drop semesters in the past / opted-out seasons,
      - drop any course code not in the catalog (fabricated codes never survive),
      - drop courses already completed (or an equivalent of),
      - overwrite name/credits from the authoritative catalog entry,
      - DEFER a course whose prerequisite is only met later: rather than flagging a
        course co-scheduled with its own prereq, carry it forward to a subsequent
        semester where the prereq is already satisfied. GPA-gated courses are NOT
        deferred (rescheduling can't change the student's current GPA) — they stay
        flagged. Courses that can't be placed within the timeline surface a warning.
    """
    all_existing_codes = ctx["all_codes"]
    catalog = ctx.get("catalog", {})
    gpa_by_scope = ctx.get("gpa_by_scope", {})
    already_completed = set(ctx.get("completed_codes", set()))
    scheduled_before = set(already_completed)

    kept = [
        sem
        for sem in sorted(plan.get("semesters", []), key=lambda s: _term_sort_key(s.get("term", "")))
        if not _semester_is_past_or_current(sem.get("term", ""))
        and not _is_skipped_season(sem.get("term", ""), ctx)
    ]

    placed_codes: set[str] = set()
    deferred: list[dict] = []          # courses waiting for a prereq scheduled later
    dropped_overflow: list[str] = []   # courses dropped for lack of room
    cleaned_semesters = []

    for idx, sem in enumerate(kept):
        is_last = idx == len(kept) - 1
        pool = deferred + list(sem.get("courses", []))
        deferred = []
        courses: list[dict] = []
        this_codes: list[str] = []
        capped = False

        for course in pool:
            prepared = _prepare_course(
                course,
                catalog=catalog,
                all_existing_codes=all_existing_codes,
                already_completed=already_completed,
                placed_codes=placed_codes,
                this_codes=this_codes,
            )
            if prepared is None:
                continue
            code, entry = prepared

            # Defer a course whose prerequisite is missing NOW but could be met in a
            # later semester (only when this isn't the final semester).
            if entry is not None and not is_last:
                if missing_prerequisite_group(entry.get("prerequisites"), scheduled_before):
                    deferred.append(course)
                    continue

            # Capacity: carry overflow forward, or drop on the last semester (matches
            # the historical hard cap so nothing balloons past MAX_COURSES).
            if len(courses) >= MAX_COURSES_PER_SEMESTER:
                capped = True
                if is_last:
                    dropped_overflow.append(code)
                else:
                    deferred.append(course)
                continue

            # Flag any remaining eligibility issue (GPA gate, or an unmet prereq on the
            # final semester where we can no longer defer).
            if entry is not None:
                blocked_reason = evaluate_entry(
                    entry, scheduled_before, gpa_by_scope, plan_phrasing=True
                )
                if blocked_reason:
                    course["blocked_reason"] = blocked_reason
                else:
                    course.pop("blocked_reason", None)

            courses.append(course)
            this_codes.append(code)

        if capped:
            sem["semester_notes"] = (sem.get("semester_notes") or "") + f" (Capped to {MAX_COURSES_PER_SEMESTER} courses)"

        scheduled_before.update(this_codes)
        placed_codes.update(this_codes)
        if courses:
            sem["courses"] = courses
            cleaned_semesters.append(sem)

    plan["semesters"] = cleaned_semesters

    stuck = sorted({normalize_course_code(c.get("course_code", "")) for c in deferred} | set(dropped_overflow))
    stuck = [c for c in stuck if c]
    if stuck:
        plan.setdefault("warnings", []).append(
            "Not enough room in the planned semesters for: "
            + ", ".join(stuck)
            + ". Consider adding Summer terms or an extra year."
        )
    return plan


def _pad_plan_to_target(plan: dict, ctx: dict) -> dict:
    """Fill spare capacity in the planned semesters with elective placeholders so the
    plan trends toward the degree credit total (York CS honours = 120). Only fills
    EXISTING future semesters (never invents terms past graduation); if the target
    still isn't reachable, adds a warning instead of over-scheduling."""
    summary = ctx.get("summary") or {}
    target = float(summary.get("total_credits_required") or 120.0)
    completed_credits = float(summary.get("total_credits_completed") or 0.0)

    semesters = plan.get("semesters", [])
    plan_codes = {
        normalize_course_code(c.get("course_code", ""))
        for s in semesters
        for c in s.get("courses", [])
    }
    # Projected credits = completed + everything in the plan + existing planned/in-progress
    # courses the plan didn't re-list.
    plan_credits = sum(float(c.get("credits", 0) or 0) for s in semesters for c in s.get("courses", []))
    extra_existing = sum(
        float(c.credit_value)
        for c in list(ctx.get("planned", [])) + list(ctx.get("in_progress", []))
        if normalize_course_code(c.course_code) not in plan_codes
    )
    gap = target - (completed_credits + plan_credits + extra_existing)
    if gap < 3:
        return plan

    needed = int(gap // 3)
    added = 0
    for sem in semesters:
        while len(sem.get("courses", [])) < MAX_COURSES_PER_SEMESTER and added < needed:
            sem.setdefault("courses", []).append({
                "course_code": "ELECTIVE",
                "course_name": "Elective (your choice — toward the 120-credit total)",
                "credits": 3.0,
                "requirement_bucket": "Electives",
                "reasoning": "Fills remaining elective credits required to reach the degree total.",
                "prerequisites": "None",
                "already_in_plan": False,
                "is_placeholder": True,
            })
            added += 1

    if added < needed:
        remaining = (needed - added) * 3
        plan.setdefault("warnings", []).append(
            f"About {remaining:.0f} more elective credits are needed to reach {target:.0f} "
            "beyond the scheduled semesters — consider Summer terms or an extra year."
        )
    return plan


def _stream_prepare_semester(
    sem: dict, ctx: dict, scheduled_accum: set, placed_accum: set
) -> bool:
    """Validate one STREAMED semester in place: drop fabricated / already-completed /
    duplicate courses, overwrite name/credits from the catalog, cap, and flag
    eligibility against the courses accumulated so far. Returns True if any course
    remains. (Streaming emits semesters as they arrive, so it can't defer across
    not-yet-seen terms — it flags rather than reorders.)"""
    catalog = ctx.get("catalog", {})
    gpa_by_scope = ctx.get("gpa_by_scope", {})
    all_existing = ctx["all_codes"]
    already_completed = set(ctx.get("completed_codes", set()))

    kept: list[dict] = []
    this_codes: list[str] = []
    for course in sem.get("courses", []):
        if len(kept) >= MAX_COURSES_PER_SEMESTER:
            break
        prepared = _prepare_course(
            course,
            catalog=catalog,
            all_existing_codes=all_existing,
            already_completed=already_completed,
            placed_codes=placed_accum,
            this_codes=this_codes,
        )
        if prepared is None:
            continue
        _code, entry = prepared
        if entry is not None:
            blocked_reason = evaluate_entry(entry, scheduled_accum, gpa_by_scope, plan_phrasing=True)
            if blocked_reason:
                course["blocked_reason"] = blocked_reason
            else:
                course.pop("blocked_reason", None)
        kept.append(course)
        this_codes.append(_code)

    sem["courses"] = kept
    scheduled_accum.update(this_codes)
    placed_accum.update(this_codes)
    return bool(kept)


async def generate_semester_plan(
    user_id: uuid.UUID,
    db: AsyncSession,
    skip_summers: bool = False,
    skip_winters: bool = False,
) -> dict:
    """Generate a full AI-powered semester plan."""
    ctx = await _gather_context(user_id, db, skip_summers=skip_summers, skip_winters=skip_winters)

    prompt = _build_prompt(ctx)

    client = get_groq_client()
    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=8192,
    )
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        plan = json.loads(text)
    except json.JSONDecodeError:
        plan = {
            "plan_summary": "Failed to parse plan. Raw AI response below.",
            "semesters": [],
            "warnings": [text[:500]],
        }

    # Hard-enforce constraints the AI may have violated, then top up toward the
    # degree credit total with elective placeholders.
    plan = _sanitize_plan(plan, ctx)
    plan = _pad_plan_to_target(plan, ctx)

    return plan


def _extract_json_from_stream(accumulated: str) -> str | None:
    """Try to extract a complete JSON object from accumulated streamed text."""
    text = accumulated.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if "```" in text:
            text = text.rsplit("```", 1)[0]
    # Find the outermost { ... }
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _try_parse_partial_semesters(accumulated: str) -> tuple[dict | None, list[dict]]:
    """Attempt to parse plan_summary and complete semester objects from partial JSON.

    Returns (partial_plan_info, list_of_complete_semesters_so_far).
    """
    text = accumulated.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if "```" in text:
            text = text.rsplit("```", 1)[0]

    plan_summary = None
    semesters = []

    # Try to extract plan_summary
    summary_match = re.search(r'"plan_summary"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if summary_match:
        plan_summary = summary_match.group(1).replace('\\"', '"').replace("\\n", "\n")

    # Find semesters array content and parse complete semester objects
    sem_start = text.find('"semesters"')
    if sem_start == -1:
        return ({"plan_summary": plan_summary} if plan_summary else None, [])

    # Find the opening bracket of the semesters array
    bracket_pos = text.find("[", sem_start)
    if bracket_pos == -1:
        return ({"plan_summary": plan_summary} if plan_summary else None, [])

    # Walk through finding complete {...} objects in the array
    pos = bracket_pos + 1
    while pos < len(text):
        # Skip whitespace and commas
        while pos < len(text) and text[pos] in " \t\n\r,":
            pos += 1
        if pos >= len(text) or text[pos] == "]":
            break
        if text[pos] != "{":
            pos += 1
            continue

        # Try to find matching closing brace
        depth = 0
        in_str = False
        esc = False
        start_pos = pos
        found = False
        for i in range(pos, len(text)):
            ch = text[i]
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        sem_obj = json.loads(text[start_pos : i + 1])
                        semesters.append(sem_obj)
                    except json.JSONDecodeError:
                        pass
                    pos = i + 1
                    found = True
                    break
        if not found:
            break  # Incomplete object — still streaming

    return ({"plan_summary": plan_summary} if plan_summary else None, semesters)


async def generate_semester_plan_stream(
    user_id: uuid.UUID,
    db: AsyncSession,
    skip_summers: bool = False,
    skip_winters: bool = False,
):
    """Generate an AI semester plan using true Gemini streaming, yielding SSE events
    as each semester becomes available.

    Yields SSE-formatted strings: "data: <json>\\n\\n"
    Event types:
      - {"type": "summary", "plan_summary": "..."}
      - {"type": "semester", "semester": {...}, "index": N}
      - {"type": "warnings", "warnings": [...]}
      - {"type": "done"}
      - {"type": "error", "message": "..."}
    """
    import asyncio

    try:
        ctx = await _gather_context(user_id, db, skip_summers=skip_summers, skip_winters=skip_winters)
        prompt = _build_prompt(ctx)

        client = get_groq_client()
        stream = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8192,
            stream=True,
        )

        accumulated = ""
        summary_sent = False
        semesters_sent = 0
        # Accumulators for per-semester catalog validation + eligibility flagging,
        # mirroring _sanitize_plan for the non-streaming path.
        scheduled_accum = set(ctx.get("completed_codes", set()))
        placed_accum: set[str] = set()

        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if not delta:
                continue
            accumulated += delta

            # Try to send summary as soon as it's available
            if not summary_sent:
                partial_info, partial_sems = _try_parse_partial_semesters(accumulated)
                if partial_info and partial_info.get("plan_summary"):
                    yield f"data: {json.dumps({'type': 'summary', 'plan_summary': partial_info['plan_summary']})}\n\n"
                    summary_sent = True

            # Try to parse and send new complete semesters
            _, parsed_semesters = _try_parse_partial_semesters(accumulated)
            while semesters_sent < len(parsed_semesters):
                sem = parsed_semesters[semesters_sent]
                term = sem.get("term", "")
                if _semester_is_past_or_current(term) or _is_skipped_season(term, ctx):
                    semesters_sent += 1
                    continue
                # Validate against the catalog (drop fabricated/completed/dupes,
                # overwrite name/credits, flag eligibility). Skip emitting if empty.
                has_courses = _stream_prepare_semester(sem, ctx, scheduled_accum, placed_accum)
                semesters_sent += 1
                if not has_courses:
                    continue

                yield f"data: {json.dumps({'type': 'semester', 'semester': sem, 'index': semesters_sent - 1})}\n\n"

            # Yield control to event loop so SSE events flush
            await asyncio.sleep(0)

        # Final parse of the complete response
        full_json = _extract_json_from_stream(accumulated)
        if full_json:
            try:
                plan = json.loads(full_json)

                # Send summary if we haven't yet
                if not summary_sent and plan.get("plan_summary"):
                    yield f"data: {json.dumps({'type': 'summary', 'plan_summary': plan['plan_summary']})}\n\n"

                # Send any remaining semesters
                all_semesters = plan.get("semesters", [])
                for i in range(semesters_sent, len(all_semesters)):
                    sem = all_semesters[i]
                    term = sem.get("term", "")
                    if _semester_is_past_or_current(term) or _is_skipped_season(term, ctx):
                        continue
                    if not _stream_prepare_semester(sem, ctx, scheduled_accum, placed_accum):
                        continue
                    yield f"data: {json.dumps({'type': 'semester', 'semester': sem, 'index': i})}\n\n"

                # Send warnings
                warnings = plan.get("warnings", [])
                if warnings:
                    yield f"data: {json.dumps({'type': 'warnings', 'warnings': warnings})}\n\n"

            except json.JSONDecodeError:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to parse AI response.'})}\n\n"
                return

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception:
        logger.exception("Semester plan stream error")
        yield f"data: {json.dumps({'type': 'error', 'message': 'Plan generation failed. Please try again.'})}\n\n"


async def apply_semester_plan(
    user_id: uuid.UUID,
    semesters: list[dict],
    db: AsyncSession,
) -> dict:
    """Apply (save) the AI-generated plan — add courses that aren't already in the plan."""
    # Get existing course codes
    courses_result = await db.execute(select(Course).where(Course.user_id == user_id))
    existing = {c.course_code for c in courses_result.scalars().all()}

    # Get requirement bucket mapping
    reqs_result = await db.execute(select(DegreeRequirement).where(DegreeRequirement.user_id == user_id))
    bucket_map = {r.bucket_name: r.id for r in reqs_result.scalars().all()}

    added = 0
    skipped = 0
    for sem in semesters:
        term = sem.get("term", "")

        # Don't apply anything to past/current semesters
        if _semester_is_past_or_current(term):
            skipped += len(sem.get("courses", []))
            continue

        for course_data in sem.get("courses", []):
            code = course_data.get("course_code", "")
            if not code or code in existing:
                skipped += 1
                continue

            bucket_id = None
            bucket_name = course_data.get("requirement_bucket")
            if bucket_name and bucket_name in bucket_map:
                bucket_id = bucket_map[bucket_name]

            course = Course(
                user_id=user_id,
                course_code=code,
                course_name=course_data.get("course_name", ""),
                credit_value=course_data.get("credits", 3.0),
                status=CourseStatus.planned,
                term=term,
                requirement_bucket_id=bucket_id,
            )
            db.add(course)
            existing.add(code)
            added += 1

    await db.commit()
    return {"added": added, "skipped": skipped}
