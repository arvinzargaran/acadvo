import json
import logging
import time
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.client import acomplete, get_groq_client
from app.config import settings
from app.models.user import User
from app.models.degree import Assessment, DegreeRequirement, Course, CourseStatus
from app.models.project import Project, Milestone, MilestoneStatus
from app.models.career import CareerTarget, CareerStatus, TimelineEvent, TimelineCategory
from app.models.suggestion import AISuggestion, SuggestionType, RiskSeverity

logger = logging.getLogger("acadvo.ai")

UNIVERSITY_DOMAINS = {
    "University of Guelph": "uoguelph.ca",
    "University of Toronto": "utoronto.ca",
    "University of Waterloo": "uwaterloo.ca",
    "University of British Columbia": "ubc.ca",
    "McGill University": "mcgill.ca",
    "University of Alberta": "ualberta.ca",
    "McMaster University": "mcmaster.ca",
    "Queen's University": "queensu.ca",
    "Western University": "uwo.ca",
    "University of Ottawa": "uottawa.ca",
    "University of Calgary": "ucalgary.ca",
    "Simon Fraser University": "sfu.ca",
    "Dalhousie University": "dal.ca",
    "University of Victoria": "uvic.ca",
    "York University": "yorku.ca",
    "Toronto Metropolitan University": "torontomu.ca",
    "Carleton University": "carleton.ca",
    "Concordia University": "concordia.ca",
    "University of Manitoba": "umanitoba.ca",
    "University of Saskatchewan": "usask.ca",
    "Memorial University": "mun.ca",
    "Wilfrid Laurier University": "wlu.ca",
    "Ontario Tech University": "ontariotechu.ca",
    "University of Windsor": "uwindsor.ca",
    "University of New Brunswick": "unb.ca",
    "Brock University": "brocku.ca",
}

def _require(inp: dict, *keys: str) -> str | None:
    missing = [k for k in keys if k not in inp or inp[k] is None]
    return f"Missing required fields: {', '.join(missing)}" if missing else None


async def execute_tool(
    tool_name: str,
    tool_input: dict,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    db: AsyncSession,
) -> str:
    """Execute an AI tool call and return a JSON string result.

    Observability: logs the tool name, wall-clock duration, and outcome. Tool
    arguments and results are NEVER logged — they contain user data.
    """
    start = time.perf_counter()
    try:
        handler = TOOL_HANDLERS.get(tool_name)
        if handler is None:
            logger.warning(
                "unknown tool",
                extra={"tool": tool_name, "status": "unknown"},
            )
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        result = await handler(tool_input, user_id, conversation_id, db)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        status = "error" if isinstance(result, dict) and result.get("error") else "success"
        logger.debug(
            "tool executed",
            extra={"tool": tool_name, "duration_ms": duration_ms, "status": status},
        )
        return json.dumps(result, default=str)
    except Exception as e:
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        # Log the stack trace before returning the error to the model (existing
        # error-handling semantics are unchanged; this only adds visibility).
        logger.exception(
            "tool execution failed",
            extra={"tool": tool_name, "duration_ms": duration_ms, "status": "exception"},
        )
        return json.dumps({"error": str(e)})

async def _get_degree_summary(inp: dict, user_id: uuid.UUID, conv_id: uuid.UUID | None, db: AsyncSession) -> dict:
    # Delegate to the service layer so logic stays in one place
    from app.services.degree import get_degree_summary
    return await get_degree_summary(user_id, db)

async def _suggest_courses(inp: dict, user_id: uuid.UUID, conv_id: uuid.UUID | None, db: AsyncSession) -> dict:
    # Return current state so the AI can reason about what to suggest
    summary = await _get_degree_summary(inp, user_id, conv_id, db)
    at_risk = [b for b in summary["buckets"] if b["at_risk"]]
    return {
        "semester": inp.get("semester"),
        "goal": inp.get("goal"),
        "degree_summary": summary,
        "at_risk_buckets": at_risk,
        "note": "Based on this data, recommend specific courses. Use add_course to save them once the student confirms.",
    }

async def _add_course(inp: dict, user_id: uuid.UUID, conv_id: uuid.UUID | None, db: AsyncSession) -> dict:
    if err := _require(inp, "course_code", "course_name", "credit_value"):
        return {"error": err}

    # Reuse the same catalog + eligibility logic that grounds recommendations, so
    # the AI can never write a course the student is not actually eligible for and
    # never persist a fabricated code / wrong name-credits it made up in chat.
    from app.services.catalog import get_catalog
    from app.services.document_parser import normalize_course_code
    from app.services.eligibility import (
        evaluate_entry,
        get_completed_codes,
        gpa_by_scope_for_catalog,
    )

    # Fetch the user (needed for .university, and the model doesn't have it yet).
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()

    # Canonicalise the code up front — dedupe, catalog lookup and the stored row
    # all key off the normalized form so we never create inconsistent-prefix twins.
    code = normalize_course_code(inp["course_code"])
    course_name = inp["course_name"]
    credit_value = inp["credit_value"]
    term = inp.get("term")

    # Dedupe: refuse if the student already has this canonical code on their plan.
    existing_result = await db.execute(select(Course).where(Course.user_id == user_id))
    for existing in existing_result.scalars():
        if normalize_course_code(existing.course_code) == code:
            return {
                "error": f"{code} is already on this student's plan; not adding a duplicate.",
                "duplicate": True,
                "course_id": str(existing.id),
            }

    # Catalog-grounded eligibility check. Fail OPEN when the code isn't in the
    # catalog (unseeded / other university) — allow the add but still normalize.
    catalog = await get_catalog(user.university or "York University", db, user_id=user_id)
    entry = catalog.get(code)
    if entry is not None:
        satisfied = await get_completed_codes(user_id, db)
        gpa_by_scope = await gpa_by_scope_for_catalog(catalog, user_id, db)
        blocked = evaluate_entry(entry, satisfied, gpa_by_scope)
        if blocked:
            return {
                "error": f"Cannot add {code}: {blocked}",
                "blocked_reason": blocked,
            }
        # Eligible AND in the catalog — trust the catalog, not the model's text.
        course_name = entry["course_name"]
        credit_value = entry["credits"]

    # Find the requirement bucket by name
    bucket_id = None
    bucket_name = inp.get("requirement_bucket")
    if bucket_name:
        result = await db.execute(
            select(DegreeRequirement).where(
                DegreeRequirement.user_id == user_id,
                DegreeRequirement.bucket_name == bucket_name,
            )
        )
        bucket = result.scalar_one_or_none()
        if bucket:
            bucket_id = bucket.id

    course = Course(
        user_id=user_id,
        course_code=code,
        course_name=course_name,
        credit_value=credit_value,
        status=CourseStatus(inp.get("status", "planned")),
        term=term,
        requirement_bucket_id=bucket_id,
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)

    return {
        "success": True,
        "course_id": str(course.id),
        "message": f"Added {course.course_code} ({course.course_name}) to {term or 'unscheduled'} as {course.status.value}",
    }

async def _update_course_status(inp: dict, user_id: uuid.UUID, conv_id: uuid.UUID | None, db: AsyncSession) -> dict:
    if err := _require(inp, "course_id"):
        return {"error": err}
    result = await db.execute(
        select(Course).where(Course.id == uuid.UUID(inp["course_id"]), Course.user_id == user_id)
    )
    course = result.scalar_one_or_none()
    if not course:
        return {"error": "Course not found"}

    # No-op guard: a read-only intent ("what is my status/grade?") must never turn
    # into a write. Only mutate — and only commit — on a REAL change.
    changed = False
    if "status" in inp:
        new_status = CourseStatus(inp["status"])
        if course.status != new_status:
            course.status = new_status
            changed = True
    if "grade" in inp and course.grade != inp["grade"]:
        course.grade = inp["grade"]
        changed = True

    if not changed:
        return {
            "success": True,
            "no_op": True,
            "message": f"No change: {course.course_code} is already status={course.status.value}, grade={course.grade}.",
        }

    await db.commit()
    return {
        "success": True,
        "message": f"Updated {course.course_code}: status={course.status.value}, grade={course.grade}",
    }

async def _create_project(inp: dict, user_id: uuid.UUID, conv_id: uuid.UUID | None, db: AsyncSession) -> dict:
    if err := _require(inp, "name", "priority"):
        return {"error": err}
    hard_deadline = None
    if inp.get("hard_deadline"):
        hard_deadline = date.fromisoformat(inp["hard_deadline"])

    project = Project(
        user_id=user_id,
        name=inp["name"],
        description=inp.get("description"),
        priority=inp["priority"],
        tech_stack=inp.get("tech_stack"),
        hard_deadline=hard_deadline,
        product_framing=inp.get("product_framing"),
    )
    db.add(project)
    await db.flush()

    milestones_data = inp.get("milestones", [])
    for m in milestones_data:
        target_date = None
        if m.get("target_date"):
            target_date = date.fromisoformat(m["target_date"])
        milestone = Milestone(
            project_id=project.id,
            title=m["title"],
            description=m.get("description"),
            target_date=target_date,
            order_index=m.get("order_index", 0),
        )
        db.add(milestone)

    await db.commit()
    await db.refresh(project)

    return {
        "success": True,
        "project_id": str(project.id),
        "message": f"Created project '{project.name}' with {len(milestones_data)} milestones",
    }

async def _update_milestone_status(inp: dict, user_id: uuid.UUID, conv_id: uuid.UUID | None, db: AsyncSession) -> dict:
    if err := _require(inp, "milestone_id", "status"):
        return {"error": err}
    result = await db.execute(
        select(Milestone)
        .join(Project)
        .where(Milestone.id == uuid.UUID(inp["milestone_id"]), Project.user_id == user_id)
    )
    milestone = result.scalar_one_or_none()
    if not milestone:
        return {"error": "Milestone not found"}

    milestone.status = MilestoneStatus(inp["status"])
    if inp["status"] == "complete":
        milestone.completed_at = datetime.now(timezone.utc)

    await db.commit()
    return {
        "success": True,
        "message": f"Updated milestone '{milestone.title}' to {milestone.status.value}",
    }

async def _add_career_target(inp: dict, user_id: uuid.UUID, conv_id: uuid.UUID | None, db: AsyncSession) -> dict:
    if err := _require(inp, "company_name"):
        return {"error": err}
    target = CareerTarget(
        user_id=user_id,
        company_name=inp["company_name"],
        role_type=inp.get("role_type"),
        location=inp.get("location"),
        target_term=inp.get("target_term"),
        notes=inp.get("notes"),
    )
    db.add(target)
    await db.commit()
    await db.refresh(target)

    return {
        "success": True,
        "target_id": str(target.id),
        "message": f"Added {target.company_name} to career targets",
    }

async def _update_career_target(inp: dict, user_id: uuid.UUID, conv_id: uuid.UUID | None, db: AsyncSession) -> dict:
    if err := _require(inp, "target_id"):
        return {"error": err}
    result = await db.execute(
        select(CareerTarget).where(
            CareerTarget.id == uuid.UUID(inp["target_id"]),
            CareerTarget.user_id == user_id,
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        return {"error": "Career target not found"}

    if "status" in inp:
        target.status = CareerStatus(inp["status"])
    if "notes" in inp:
        target.notes = inp["notes"]

    await db.commit()
    return {
        "success": True,
        "message": f"Updated {target.company_name}: status={target.status.value}",
    }

async def _flag_risk(inp: dict, user_id: uuid.UUID, conv_id: uuid.UUID | None, db: AsyncSession) -> dict:
    if err := _require(inp, "description", "severity"):
        return {"error": err}
    suggestion = AISuggestion(
        user_id=user_id,
        conversation_id=conv_id,
        suggestion_type=SuggestionType.risk_flag,
        content=inp["description"],
        severity=RiskSeverity(inp["severity"]),
    )
    db.add(suggestion)
    await db.commit()

    return {
        "success": True,
        "message": f"Risk flagged ({inp['severity']}): {inp['description'][:100]}",
    }

async def _generate_timeline(inp: dict, user_id: uuid.UUID, conv_id: uuid.UUID | None, db: AsyncSession) -> dict:
    events_created = []
    for evt in inp.get("events", []):
        event = TimelineEvent(
            user_id=user_id,
            title=evt["title"],
            description=evt.get("description"),
            event_date=date.fromisoformat(evt["event_date"]),
            category=TimelineCategory(evt["category"]),
            is_hard_deadline=evt.get("is_hard_deadline", False),
        )
        db.add(event)
        events_created.append(evt["title"])

    await db.commit()
    return {
        "success": True,
        "events_created": len(events_created),
        "message": f"Created {len(events_created)} timeline events",
    }

async def _update_user_profile(inp: dict, user_id: uuid.UUID, conv_id: uuid.UUID | None, db: AsyncSession) -> dict:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()

    updated_fields = []
    for field in ["university", "program", "start_year", "expected_graduation_year", "country", "city", "career_target", "onboarding_complete"]:
        if field in inp:
            setattr(user, field, inp[field])
            updated_fields.append(field)

    await db.commit()
    return {
        "success": True,
        "updated_fields": updated_fields,
        "message": f"Updated profile: {', '.join(updated_fields)}",
    }

async def _search_course_recommendations(inp: dict, user_id: uuid.UUID, conv_id: uuid.UUID | None, db: AsyncSession) -> dict:
    # Fetch user context
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()

    # Fetch degree summary for context
    summary = await _get_degree_summary({}, user_id, conv_id, db)
    at_risk = [b for b in summary["buckets"] if b["at_risk"]]

    # Fetch career targets
    career_result = await db.execute(
        select(CareerTarget).where(CareerTarget.user_id == user_id)
    )
    targets = career_result.scalars().all()
    target_info = ", ".join(f"{t.company_name} ({t.role_type})" for t in targets) or "none specified"

    focus = inp.get("focus_area", "general")
    semester = inp.get("semester", "upcoming")
    bucket = inp.get("requirement_bucket", "")

    prompt = f"""Recommend elective and optional courses at {user.university or 'their university'} for a {user.program or 'computer science'} student.

Focus area: {focus}
Target semester: {semester}
{f'Requirement bucket to fill: {bucket}' if bucket else ''}
Career goals: {user.career_target or 'not specified'}
Target companies/roles: {target_info}

At-risk requirement buckets needing credits: {json.dumps(at_risk) if at_risk else 'none'}

Find 5-8 specific courses with:
- Course code and name
- Credit value
- Which requirement bucket it could satisfy
- Why it's relevant to their career goals
- A brief description

Format the results as a JSON array of objects with keys: course_code, course_name, credit_value, requirement_bucket, relevance, description"""

    try:
        client = get_groq_client()
        response = await acomplete(
            client,
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        recommendations = response.choices[0].message.content
    except Exception:
        recommendations = None

    if recommendations:
        return {
            "recommendations": recommendations,
            "user_context": {
                "university": user.university,
                "program": user.program,
                "career_target": user.career_target,
                "focus_area": focus,
            },
            "note": "Present these recommendations to the student. Offer to add any they like using add_course.",
        }
    else:
        return {
            "status": "search_unavailable",
            "user_context": {
                "university": user.university,
                "program": user.program,
                "career_target": user.career_target,
                "focus_area": focus,
                "at_risk_buckets": at_risk,
                "target_companies": target_info,
            },
            "note": "Use your training knowledge to suggest courses for this student's university and program. Offer to add any they confirm using add_course.",
        }

async def _add_degree_requirement(inp: dict, user_id: uuid.UUID, conv_id: uuid.UUID | None, db: AsyncSession) -> dict:
    if err := _require(inp, "bucket_name", "credits_required"):
        return {"error": err}
    req = DegreeRequirement(
        user_id=user_id,
        bucket_name=inp["bucket_name"],
        credits_required=inp["credits_required"],
        description=inp.get("description"),
        notes=inp.get("notes"),
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)

    return {
        "success": True,
        "requirement_id": str(req.id),
        "message": f"Added degree requirement: {req.bucket_name} ({req.credits_required} credits)",
    }

async def _generate_semester_plan(inp: dict, user_id: uuid.UUID, conv_id: uuid.UUID | None, db: AsyncSession) -> dict:
    from app.services.semester_plan import generate_semester_plan
    plan = await generate_semester_plan(user_id, db)
    return {
        "plan": plan,
        "note": "Present this semester plan to the student. Show each semester with its courses and reasoning. Ask if they want to apply it (they can do so from the Course Advisor or Degree page).",
    }

async def _get_course_assessments(inp: dict, user_id: uuid.UUID, conv_id: uuid.UUID | None, db: AsyncSession) -> dict:
    course_code = inp.get("course_code", "").strip()
    if not course_code:
        return {"error": "course_code is required"}

    # Find course by code (case-insensitive, partial match)
    result = await db.execute(
        select(Course).where(
            Course.user_id == user_id,
            Course.course_code.ilike(f"%{course_code}%"),
        )
    )
    course = result.scalar_one_or_none()
    if not course:
        return {"error": f"No course found matching '{course_code}'"}

    # Get assessments
    assessments_result = await db.execute(
        select(Assessment).where(Assessment.course_id == course.id)
    )
    assessments = list(assessments_result.scalars().all())

    if not assessments:
        return {
            "course_code": course.course_code,
            "course_name": course.course_name,
            "assessments": [],
            "note": "No assessments found. The student can upload a syllabus to extract assessments.",
        }

    total_weight = sum(a.weight for a in assessments)
    return {
        "course_code": course.course_code,
        "course_name": course.course_name,
        "total_weight_found": total_weight,
        "assessments": [
            {
                "title": a.title,
                "due_date": a.due_date.isoformat() if a.due_date else None,
                "weight": a.weight,
                "category": a.category.value if hasattr(a.category, "value") else a.category,
                "notes": a.notes,
            }
            for a in sorted(assessments, key=lambda x: (x.due_date or datetime.max.replace(tzinfo=timezone.utc)))
        ],
    }

async def _search_and_recommend_courses(inp: dict, user_id: uuid.UUID, conv_id: uuid.UUID | None, db: AsyncSession) -> dict:
    from app.services.course_recommendation import generate_recommendations
    semester = inp.get("semester", "Fall 2026")
    goal = inp.get("goal", "both")
    bucket = inp.get("requirement_bucket")

    recs = await generate_recommendations(user_id, semester, goal, bucket, db)
    return {
        "semester": semester,
        "recommendations_count": len(recs),
        "recommendations": [
            {
                "course_code": r.course_code,
                "course_name": r.course_name,
                "credits": float(r.credits),
                "requirement_bucket": r.requirement_bucket,
                "reasoning": r.reasoning,
                "career_relevance": r.career_relevance,
                "prerequisites": r.prerequisite_notes,
                "priority": r.priority,
            }
            for r in recs
        ],
        "note": "Present these recommendations to the student with reasoning. They can accept them from the Course Advisor page.",
    }

TOOL_HANDLERS = {
    "get_degree_summary": _get_degree_summary,
    "suggest_courses": _suggest_courses,
    "add_course": _add_course,
    "update_course_status": _update_course_status,
    "create_project": _create_project,
    "update_milestone_status": _update_milestone_status,
    "add_career_target": _add_career_target,
    "update_career_target": _update_career_target,
    "flag_risk": _flag_risk,
    "generate_timeline": _generate_timeline,
    "update_user_profile": _update_user_profile,
    "add_degree_requirement": _add_degree_requirement,
    "get_course_assessments": _get_course_assessments,
    "search_course_recommendations": _search_course_recommendations,
    "search_and_recommend_courses": _search_and_recommend_courses,
    "generate_semester_plan": _generate_semester_plan,
}
