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
from app.services.degree import get_degree_summary

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
6. Search the ACTUAL {user.university or 'university'} course catalog{f' at {domain}' if domain else ''} for real courses with correct course codes.
7. Consider PREREQUISITES: don't schedule a course before its prerequisites are completed.
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


def _sanitize_plan(plan: dict, ctx: dict) -> dict:
    """Post-process the AI plan to enforce hard constraints."""
    all_existing_codes = ctx["all_codes"]  # all codes already in the DB

    cleaned_semesters = []
    for sem in plan.get("semesters", []):
        term = sem.get("term", "")

        # Drop semesters that are in the past or current
        if _semester_is_past_or_current(term):
            continue

        # Drop semesters the user opted out of
        if _is_skipped_season(term, ctx):
            continue

        # Filter out courses that already exist in the student's plan
        courses = []
        for course in sem.get("courses", []):
            code = course.get("course_code", "")
            if code in all_existing_codes:
                course["already_in_plan"] = True
            else:
                course["already_in_plan"] = False
            courses.append(course)

        # Enforce max courses per semester
        if len(courses) > MAX_COURSES_PER_SEMESTER:
            courses = courses[:MAX_COURSES_PER_SEMESTER]
            sem.setdefault("semester_notes", "")
            sem["semester_notes"] += f" (Capped to {MAX_COURSES_PER_SEMESTER} courses)"

        if courses:
            sem["courses"] = courses
            cleaned_semesters.append(sem)

    plan["semesters"] = cleaned_semesters
    return plan


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

    # Hard-enforce constraints the AI may have violated
    plan = _sanitize_plan(plan, ctx)

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
                # Sanitize this semester
                term = sem.get("term", "")
                if _semester_is_past_or_current(term) or _is_skipped_season(term, ctx):
                    semesters_sent += 1
                    continue
                # Mark already_in_plan
                for course in sem.get("courses", []):
                    code = course.get("course_code", "")
                    course["already_in_plan"] = code in ctx["all_codes"]
                # Cap courses
                if len(sem.get("courses", [])) > MAX_COURSES_PER_SEMESTER:
                    sem["courses"] = sem["courses"][:MAX_COURSES_PER_SEMESTER]

                yield f"data: {json.dumps({'type': 'semester', 'semester': sem, 'index': semesters_sent})}\n\n"
                semesters_sent += 1

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
                    for course in sem.get("courses", []):
                        code = course.get("course_code", "")
                        course["already_in_plan"] = code in ctx["all_codes"]
                    if len(sem.get("courses", [])) > MAX_COURSES_PER_SEMESTER:
                        sem["courses"] = sem["courses"][:MAX_COURSES_PER_SEMESTER]
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
