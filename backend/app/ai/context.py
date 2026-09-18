import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.degree import DegreeRequirement, Course, CourseStatus
from app.models.project import Project, ProjectStatus, MilestoneStatus
from app.models.career import CareerTarget, TimelineEvent
from app.models.suggestion import AISuggestion
from app.data.program_config import get_major_gpa_gates
from app.services.catalog import get_catalog, has_seeded_catalog
from app.services.degree import _is_constraint_bucket, calculate_gpa
from app.services.document_parser import normalize_course_code
from app.ai.sanitize import sanitize, untrusted_data_rule
from app.services.eligibility import format_prereqs


# The instruction block is a module-level template rather than an inline
# f-string. Same output, but the prompt text is separated from the assembly
# logic — and it stops Bandit's B608 heuristic from reading an interpolated
# string containing the words "update ... from" as SQL construction.
_INSTRUCTIONS_TEMPLATE = """
{sep}
INSTRUCTIONS
{sep}
{untrusted_data_rule}

You have tools to read and write to this student's data. Use write tools ONLY when the student explicitly asks to change their plan (add/drop a course, create a project, update a status). For questions about status, eligibility, GPA, or "can I take X" — ANSWER from the context above; do NOT call write tools. Never add or mark a course the student has not asked you to change, and never add a course whose prerequisites are unmet or whose GPA gate they fail.

{catalog_rule}

{gate_rule}

When giving advice:
- Be specific, not generic. Reference their actual courses, projects, and deadlines.
- Work backwards from deadlines. If something is at risk, say so directly.
- Prioritize actions. Don't give a list of 10 things — give the top 3.
- When suggesting courses, consider remaining requirements AND career goals.
- When discussing projects, think about what will impress at their target companies.

Modes:
- If onboarding_complete is false, you are in ONBOARDING MODE. Walk the student through setup step by step. Ask about: university, program, graduation year, career target, degree requirements (buckets + credits), completed/in-progress courses, projects, and target companies. Save each piece of information using the appropriate tool as soon as you receive it. When done, set onboarding_complete to true.
- If the student asks about their progress or status, enter CHECK-IN MODE. Give an honest assessment and top 3 actions.
- If the student asks about a specific topic, enter DEEP DIVE MODE. Give thorough analysis.
- Otherwise, you are in PLANNING MODE. Give concrete, actionable plans.

Always be direct. Students don't need diplomacy — they need clarity."""


async def build_system_prompt(user_id: uuid.UUID, db: AsyncSession) -> str:
    # Fetch user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()

    # Fetch degree requirements with courses
    req_result = await db.execute(
        select(DegreeRequirement)
        .where(DegreeRequirement.user_id == user_id)
        .options(selectinload(DegreeRequirement.courses))
    )
    requirements = req_result.scalars().all()

    # Fetch all courses for this user (including those without a bucket)
    courses_result = await db.execute(
        select(Course).where(Course.user_id == user_id).order_by(Course.term)
    )
    all_courses = courses_result.scalars().all()

    # Fetch projects with milestones
    proj_result = await db.execute(
        select(Project)
        .where(Project.user_id == user_id)
        .options(selectinload(Project.milestones))
        .order_by(Project.priority)
    )
    projects = proj_result.scalars().all()

    # Fetch career targets
    career_result = await db.execute(
        select(CareerTarget).where(CareerTarget.user_id == user_id)
    )
    career_targets = career_result.scalars().all()

    # Fetch upcoming timeline events
    today = date.today()
    timeline_result = await db.execute(
        select(TimelineEvent)
        .where(TimelineEvent.user_id == user_id, TimelineEvent.event_date >= today)
        .order_by(TimelineEvent.event_date)
        .limit(20)
    )
    timeline_events = timeline_result.scalars().all()

    # GPA (cumulative + major GPAs with gate status) and the real course catalog,
    # so we can surface prerequisites and GPA gates the AI must respect. We ground
    # on the student's ACTUAL university — never silently substitute York's catalog
    # for a student who set no university — and track whether that university has a
    # verified (seeded) catalog so the AI can be honest about best-effort advising.
    gpa_data = await calculate_gpa(user_id, db)
    catalog = await get_catalog(user.university or "", db, user_id)
    catalog_verified = await has_seeded_catalog(user.university, db)

    # Build the prompt
    sections = []

    # Header
    sections.append(
        "You are Acadvo, an AI academic and career advisor built for university students. "
        "You help students plan their degrees strategically, build strong portfolios, and land internships and co-ops.\n\n"
        "You are speaking with a specific student. Here is their full profile:"
    )

    # Student profile
    profile_lines = [
        "",
        "=" * 50,
        "STUDENT PROFILE",
        "=" * 50,
        f"Name: {sanitize(user.full_name)}",
    ]
    if user.university:
        profile_lines.append(f"University: {sanitize(user.university)}")
    if user.program:
        profile_lines.append(f"Program: {sanitize(user.program)}")
    if user.start_year:
        profile_lines.append(f"Start Year: {user.start_year}")
    if user.expected_graduation_year:
        profile_lines.append(f"Expected Graduation: {user.expected_graduation_year}")
    location_parts = []
    if user.country:
        location_parts.append(user.country)
    if user.city:
        location_parts.append(user.city)
    if location_parts:
        profile_lines.append(f"Location: {', '.join(location_parts)}")
    if user.career_target:
        profile_lines.append(f"Career Target: {sanitize(user.career_target)}")
    profile_lines.append(f"Onboarding Complete: {'Yes' if user.onboarding_complete else 'No'}")
    profile_lines.append(f"Today's Date: {today.isoformat()}")
    sections.append("\n".join(profile_lines))

    # Degree progress
    if requirements:
        degree_lines = [
            "",
            "=" * 50,
            "DEGREE PROGRESS",
            "=" * 50,
        ]

        total_required = 0.0
        total_completed = 0.0
        at_risk_buckets = []

        for req in requirements:
            credits_required = float(req.credits_required)
            completed_credits = sum(
                float(c.credit_value)
                for c in req.courses
                if c.status == CourseStatus.completed
            )
            in_progress_credits = sum(
                float(c.credit_value)
                for c in req.courses
                if c.status == CourseStatus.in_progress
            )
            remaining = credits_required - completed_credits
            pct = (completed_credits / credits_required * 100) if credits_required > 0 else 0

            # Constraint buckets (e.g. "Upper Year Requirement") overlap other buckets'
            # credits, so they must NOT be added to the degree total (double-counting).
            if not _is_constraint_bucket(req.bucket_name):
                total_required += credits_required
                total_completed += completed_credits

            degree_lines.append(f"\nBucket: {sanitize(req.bucket_name)} — {completed_credits:.2f} / {credits_required:.2f} credits ({pct:.1f}%)")

            # Group courses by status
            for status_label, status_val in [
                ("Completed", CourseStatus.completed),
                ("In Progress", CourseStatus.in_progress),
                ("Planned", CourseStatus.planned),
                ("Not Scheduled", CourseStatus.not_scheduled),
            ]:
                status_courses = [c for c in req.courses if c.status == status_val]
                if status_courses:
                    course_strs = []
                    for c in status_courses:
                        parts = [sanitize(c.course_code, 32)]
                        if c.term:
                            parts.append(f"({sanitize(c.term, 32)}")
                            if c.grade:
                                parts[-1] += f", {sanitize(c.grade, 8)})"
                            else:
                                parts[-1] += ")"
                        course_strs.append(" ".join(parts))
                    degree_lines.append(f"  {status_label}: {', '.join(course_strs)}")

            if remaining > credits_required * 0.5 and remaining > 0:
                at_risk_buckets.append((req.bucket_name, remaining))

        overall_pct = (total_completed / total_required * 100) if total_required > 0 else 0
        degree_lines.insert(4, f"Overall: {total_completed:.2f} / {total_required:.2f} credits completed ({overall_pct:.1f}%)")

        # GPA + gate status — insert right under the overall line.
        gpa_lines = []
        if gpa_data.get("cumulative_gpa") is not None:
            gpa_lines.append(
                f"Cumulative GPA: {gpa_data['cumulative_gpa']} (out of {gpa_data.get('scale_max', 9.0)})"
            )
        for mg in gpa_data.get("major_gpas", []):
            scope = mg.get("scope", "")
            gpa_val = mg.get("gpa")
            gate_val = float(mg.get("gate", 4.5))
            if gpa_val is None:
                continue
            if mg.get("meets_gate"):
                gpa_lines.append(
                    f"{scope} major GPA: {gpa_val} (meets the {gate_val:.2f} {scope}-major gate)"
                )
            else:
                gpa_lines.append(
                    f"{scope} major GPA: {gpa_val} (BELOW the {gate_val:.2f} {scope}-major gate)"
                )
        for i, line in enumerate(gpa_lines):
            degree_lines.insert(5 + i, line)

        for bucket_name, remaining in at_risk_buckets:
            degree_lines.append(f"\n⚠ AT-RISK: {sanitize(bucket_name)} — {remaining:.2f} credits remaining")

        # Per-course prerequisites for planned / not-scheduled courses, so the AI
        # knows what must be completed first before recommending or adding them.
        prereq_lines = []
        for c in all_courses:
            if c.status not in (CourseStatus.planned, CourseStatus.not_scheduled):
                continue
            code = normalize_course_code(c.course_code)
            entry = catalog.get(code)
            if not entry:
                continue
            prereqs = entry.get("prerequisites")
            gate = entry.get("gpa_gate")
            if not prereqs and not gate:
                continue
            bits = []
            if prereqs:
                bits.append(f"prereqs {format_prereqs(prereqs)}")
            if gate:
                bits.append(f"gate {gate.get('scope', '')} GPA ≥ {float(gate.get('min', 4.5)):.2f}")
            prereq_lines.append(f"  - {code}: {'; '.join(bits)}")
        if prereq_lines:
            degree_lines.append("\nPrerequisites / gates for planned & not-scheduled courses:")
            degree_lines.extend(prereq_lines)

        sections.append("\n".join(degree_lines))

    # Projects
    if projects:
        proj_lines = [
            "",
            "=" * 50,
            "PORTFOLIO & PROJECTS",
            "=" * 50,
        ]

        deployed_count = sum(1 for p in projects if p.status in (ProjectStatus.deployed, ProjectStatus.interview_ready))
        proj_lines.append(f"Portfolio Readiness: {deployed_count} of {len(projects)} projects deployed/ready")

        for p in projects:
            proj_lines.append(f"\nProject: {sanitize(p.name)} (Priority {p.priority}) — STATUS: {p.status.value}")
            if p.tech_stack:
                # Sanitized like every other stored field: `tech_stack` is
                # written by the `create_project` tool from model output, which
                # in turn comes from a résumé the user uploaded — so it is
                # document-derived text landing in the system prompt that holds
                # the write tools.
                proj_lines.append(f"  Tech: {sanitize(p.tech_stack)}")

            if p.milestones:
                proj_lines.append("  Milestones:")
                for m in p.milestones:
                    icon = {"complete": "✅", "in_progress": "🔄", "pending": "⬜", "overdue": "🚨"}.get(m.status.value, "⬜")
                    date_str = f", target {m.target_date.isoformat()}" if m.target_date else ""
                    proj_lines.append(f"    {icon} {sanitize(m.title)} ({m.status.value}{date_str})")

            if p.hard_deadline:
                days_left = (p.hard_deadline - today).days
                proj_lines.append(f"  Hard Deadline: {p.hard_deadline.isoformat()}")
                proj_lines.append(f"  Days Remaining: {days_left}")

        sections.append("\n".join(proj_lines))

    # Career targets
    if career_targets:
        career_lines = [
            "",
            "=" * 50,
            "CAREER TARGETS",
            "=" * 50,
        ]
        for i, ct in enumerate(career_targets, 1):
            # Every one of these is free text the student (or a tool acting on a
            # parsed document) wrote. `company_name` was sanitized and its three
            # neighbours were not, which is the whole gap: a newline in any of
            # them opens a line of its own in the system prompt just as well.
            parts = [f"{i}. {sanitize(ct.company_name)}"]
            if ct.role_type:
                parts.append(f"— {sanitize(ct.role_type)}")
            if ct.location:
                parts.append(f"— {sanitize(ct.location)}")
            if ct.target_term:
                parts.append(f"— {sanitize(ct.target_term)}")
            parts.append(f"— {ct.status.value}")
            career_lines.append(" ".join(parts))

        sections.append("\n".join(career_lines))

    # Timeline
    if timeline_events:
        timeline_lines = [
            "",
            "=" * 50,
            "UPCOMING DEADLINES & EVENTS",
            "=" * 50,
        ]
        for evt in timeline_events:
            days_away = (evt.event_date - today).days
            hard = " [HARD DEADLINE]" if evt.is_hard_deadline else ""
            timeline_lines.append(f"- {evt.event_date.isoformat()}: {sanitize(evt.title)}{hard} — {days_away} days")

        sections.append("\n".join(timeline_lines))

    # Catalog-grounding rule — verified vs best-effort — so the AI is honest about
    # what it actually knows for this student's university.
    if catalog_verified:
        catalog_rule = (
            f"COURSE CATALOG: You have a VERIFIED, seeded catalog for {user.university}. Rely on the "
            "prerequisites and GPA gates listed in DEGREE PROGRESS above. Do NOT invent course codes, "
            "prerequisites, or gates beyond what is listed there or what the student has recorded."
        )
    else:
        uni = user.university or "this student's university"
        catalog_rule = (
            f"COURSE CATALOG: There is NO verified catalog for {uni}. You must NOT assert or invent "
            "prerequisites, course eligibility, GPA gates, or specific course codes for it. Ground every "
            "recommendation ONLY in the student's own recorded courses and requirements, and clearly frame "
            "any course suggestion as best-effort that the student must confirm against their official "
            "academic calendar."
        )

    # GPA-gate rule — describe the student's ACTUAL configured gates, not York's.
    gates = get_major_gpa_gates(user.university)
    if gates:
        gate_descs = "; ".join(
            f"a {g['min']:.2f} {g['scope']}-major GPA for {g['governs']}" for g in gates
        )
        gate_rule = (
            f"GPA GATES (HARD RULES — DO NOT VIOLATE): {user.university} gates {gate_descs}. NEVER tell a "
            "student they are eligible for, or add, a course whose prerequisites are unmet or whose GPA gate "
            "they do not meet. Check the student's completed courses, their major GPA (shown above), and each "
            "course's prerequisites BEFORE recommending or adding it. If a course is out of reach, say so "
            "plainly and explain what must happen first (finish a prereq, or raise the major GPA to the gate)."
        )
    else:
        gate_rule = (
            "PREREQUISITES (HARD RULE — DO NOT VIOLATE): NEVER tell a student they are eligible for, or add, a "
            "course whose prerequisites are unmet. Check the student's completed courses and each course's "
            "prerequisites BEFORE recommending or adding it. This student's program has no configured "
            "major-GPA gate — do not invent one."
        )

    # Instructions
    sections.append(
        _INSTRUCTIONS_TEMPLATE.format(
            sep="=" * 50,
            catalog_rule=catalog_rule,
            gate_rule=gate_rule,
            untrusted_data_rule=untrusted_data_rule(),
        )
    )

    return "\n".join(sections)
