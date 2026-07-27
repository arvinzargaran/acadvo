import uuid
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.degree import Assessment, Course
from app.models.project import Milestone, Project
from app.models.career import TimelineEvent


async def get_all_user_events(user_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    """Aggregate assessments, milestones, and timeline events into a unified event list."""
    events: list[dict] = []

    # 1. Assessments (via user's courses)
    course_result = await db.execute(
        select(Course)
        .where(Course.user_id == user_id)
        .options(selectinload(Course.assessments))
    )
    courses = list(course_result.scalars().all())
    course_map = {c.id: c for c in courses}

    for course in courses:
        for a in course.assessments:
            event_date = None
            if a.due_date:
                event_date = a.due_date.date() if isinstance(a.due_date, datetime) else a.due_date
            events.append({
                "id": str(a.id),
                "title": f"{course.course_code}: {a.title}",
                "date": event_date.isoformat() if event_date else None,
                "category": "course",
                "type": a.category.value if hasattr(a.category, "value") else a.category,
                "status": "upcoming" if (event_date and event_date >= date.today()) else "past",
                "weight": a.weight,
                "source": course.course_name,
                "source_id": str(course.id),
                "notes": a.notes,
            })

    # 2. Project milestones
    project_result = await db.execute(
        select(Project)
        .where(Project.user_id == user_id)
        .options(selectinload(Project.milestones))
    )
    projects = list(project_result.scalars().all())

    for project in projects:
        for m in project.milestones:
            event_date = m.target_date
            status = m.status.value if hasattr(m.status, "value") else m.status
            events.append({
                "id": str(m.id),
                "title": f"{project.name}: {m.title}",
                "date": event_date.isoformat() if event_date else None,
                "category": "project",
                "type": "milestone",
                "status": status,
                "weight": None,
                "source": project.name,
                "source_id": str(project.id),
                "notes": m.description,
            })

    # 3. Timeline events (career / academic)
    timeline_result = await db.execute(
        select(TimelineEvent).where(TimelineEvent.user_id == user_id)
    )
    timeline_events = list(timeline_result.scalars().all())

    for t in timeline_events:
        cat = t.category.value if hasattr(t.category, "value") else t.category
        events.append({
            "id": str(t.id),
            "title": t.title,
            "date": t.event_date.isoformat() if t.event_date else None,
            "category": "career",
            "type": cat,
            "status": "upcoming" if (t.event_date and t.event_date >= date.today()) else "past",
            "weight": None,
            "source": cat.replace("_", " ").title(),
            "source_id": None,
            "notes": t.description,
        })

    # Sort by date (nulls last)
    events.sort(key=lambda e: (e["date"] is None, e["date"] or ""))

    return events
