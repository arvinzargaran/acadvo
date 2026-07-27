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
        f"Name: {user.full_name}",
    ]
    if user.university:
        profile_lines.append(f"University: {user.university}")
    if user.program:
        profile_lines.append(f"Program: {user.program}")
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
        profile_lines.append(f"Career Target: {user.career_target}")
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

            total_required += credits_required
            total_completed += completed_credits

            degree_lines.append(f"\nBucket: {req.bucket_name} — {completed_credits:.2f} / {credits_required:.2f} credits ({pct:.1f}%)")

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
                        parts = [c.course_code]
                        if c.term:
                            parts.append(f"({c.term}")
                            if c.grade:
                                parts[-1] += f", {c.grade})"
                            else:
                                parts[-1] += ")"
                        course_strs.append(" ".join(parts))
                    degree_lines.append(f"  {status_label}: {', '.join(course_strs)}")

            if remaining > credits_required * 0.5 and remaining > 0:
                at_risk_buckets.append((req.bucket_name, remaining))

        overall_pct = (total_completed / total_required * 100) if total_required > 0 else 0
        degree_lines.insert(4, f"Overall: {total_completed:.2f} / {total_required:.2f} credits completed ({overall_pct:.1f}%)")

        for bucket_name, remaining in at_risk_buckets:
            degree_lines.append(f"\n⚠ AT-RISK: {bucket_name} — {remaining:.2f} credits remaining")

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
            proj_lines.append(f"\nProject: {p.name} (Priority {p.priority}) — STATUS: {p.status.value}")
            if p.tech_stack:
                proj_lines.append(f"  Tech: {p.tech_stack}")

            if p.milestones:
                proj_lines.append("  Milestones:")
                for m in p.milestones:
                    icon = {"complete": "✅", "in_progress": "🔄", "pending": "⬜", "overdue": "🚨"}.get(m.status.value, "⬜")
                    date_str = f", target {m.target_date.isoformat()}" if m.target_date else ""
                    proj_lines.append(f"    {icon} {m.title} ({m.status.value}{date_str})")

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
            parts = [f"{i}. {ct.company_name}"]
            if ct.role_type:
                parts.append(f"— {ct.role_type}")
            if ct.location:
                parts.append(f"— {ct.location}")
            if ct.target_term:
                parts.append(f"— {ct.target_term}")
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
            timeline_lines.append(f"- {evt.event_date.isoformat()}: {evt.title}{hard} — {days_away} days")

        sections.append("\n".join(timeline_lines))

    # Instructions
    sections.append(f"""
{'=' * 50}
INSTRUCTIONS
{'=' * 50}
You have tools to read and write to this student's data. When the student asks you to add a course, create a project, update a milestone, or make any change to their plan — use the appropriate tool. Do not just describe what they should do; actually do it.

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

Always be direct. Students don't need diplomacy — they need clarity.""")

    return "\n".join(sections)
