import uuid
from collections import Counter
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.career import CareerTarget, TimelineEvent
from app.models.dsa import DSAProblem, ProblemStatus
from app.models.project import Project, ProjectStatus
from app.models.user import User
from app.schemas.career import CareerTargetCreate, CareerTargetUpdate, TimelineEventCreate


# ── Career Targets ─────────────────────────────────────────────────


async def list_career_targets(user_id: uuid.UUID, db: AsyncSession) -> list[CareerTarget]:
    result = await db.execute(
        select(CareerTarget).where(CareerTarget.user_id == user_id).order_by(CareerTarget.created_at.desc())
    )
    return list(result.scalars().all())


async def create_career_target(
    user_id: uuid.UUID, data: CareerTargetCreate, db: AsyncSession
) -> CareerTarget:
    target = CareerTarget(
        user_id=user_id,
        company_name=data.company_name,
        role_type=data.role_type,
        location=data.location,
        status=data.status,
        target_term=data.target_term,
        notes=data.notes,
    )
    db.add(target)
    await db.commit()
    await db.refresh(target)
    return target


async def update_career_target(
    target_id: uuid.UUID, user_id: uuid.UUID, data: CareerTargetUpdate, db: AsyncSession
) -> CareerTarget:
    result = await db.execute(
        select(CareerTarget).where(CareerTarget.id == target_id)
    )
    target = result.scalar_one_or_none()
    if target is None or target.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Career target not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(target, field, value)

    await db.commit()
    await db.refresh(target)
    return target


async def delete_career_target(
    target_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> None:
    result = await db.execute(
        select(CareerTarget).where(CareerTarget.id == target_id)
    )
    target = result.scalar_one_or_none()
    if target is None or target.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Career target not found")
    await db.delete(target)
    await db.commit()


# ── Timeline Events ───────────────────────────────────────────────


async def list_timeline_events(user_id: uuid.UUID, db: AsyncSession) -> list[TimelineEvent]:
    result = await db.execute(
        select(TimelineEvent).where(TimelineEvent.user_id == user_id).order_by(TimelineEvent.event_date)
    )
    return list(result.scalars().all())


async def create_timeline_event(
    user_id: uuid.UUID, data: TimelineEventCreate, db: AsyncSession
) -> TimelineEvent:
    event = TimelineEvent(
        user_id=user_id,
        title=data.title,
        description=data.description,
        event_date=data.event_date,
        category=data.category,
        is_hard_deadline=data.is_hard_deadline,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def delete_timeline_event(
    event_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> None:
    result = await db.execute(
        select(TimelineEvent).where(TimelineEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    if event is None or event.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timeline event not found")
    await db.delete(event)
    await db.commit()


# ── Readiness Score ──────────────────────────────────────────────


async def get_readiness_score(user_id: uuid.UUID, db: AsyncSession) -> dict:
    """Calculate co-op readiness score (0-100) across four categories."""
    from app.services.degree import calculate_gpa

    # 1. GPA (30 pts): (gpa / scale_max) * 30
    gpa_data = await calculate_gpa(user_id, db)
    gpa = gpa_data.get("cumulative_gpa")
    scale_max = gpa_data.get("scale_max", 4.0)
    if gpa is not None and scale_max > 0:
        gpa_score = round((gpa / scale_max) * 30, 1)
    else:
        gpa_score = 0.0

    # 2. Projects (30 pts): 3 pts per deployed/interview_ready, max 30
    projects_result = await db.execute(
        select(Project).where(
            Project.user_id == user_id,
            Project.status.in_([ProjectStatus.deployed, ProjectStatus.interview_ready]),
        )
    )
    ready_projects = list(projects_result.scalars().all())
    project_score = min(len(ready_projects) * 3.0, 30.0)

    # 3. DSA (20 pts): 4 pts per pattern with >= 3 solved problems, max 20
    dsa_result = await db.execute(
        select(DSAProblem.pattern, func.count(DSAProblem.id))
        .where(DSAProblem.user_id == user_id, DSAProblem.status == ProblemStatus.solved)
        .group_by(DSAProblem.pattern)
    )
    patterns_mastered = sum(1 for _, count in dsa_result.all() if count >= 3)
    dsa_score = min(patterns_mastered * 4.0, 20.0)

    # 4. Career (20 pts): 10 pts for 5+ active targets, 10 pts for resume reviewed in last 30 days
    targets_result = await db.execute(
        select(func.count(CareerTarget.id)).where(CareerTarget.user_id == user_id)
    )
    target_count = targets_result.scalar() or 0
    career_targets_score = 10.0 if target_count >= 5 else round((target_count / 5) * 10, 1)

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    resume_score = 0.0
    if user and user.last_resume_review:
        days_since = (datetime.now(timezone.utc) - user.last_resume_review).days
        resume_score = 10.0 if days_since <= 30 else 0.0

    career_score = career_targets_score + resume_score

    total = round(gpa_score + project_score + dsa_score + career_score)

    return {
        "total": total,
        "breakdown": {
            "gpa": {
                "score": gpa_score,
                "max": 30,
                "detail": f"GPA: {gpa}/{scale_max}" if gpa else "No grades yet",
            },
            "projects": {
                "score": project_score,
                "max": 30,
                "detail": f"{len(ready_projects)} deployed/ready projects",
            },
            "dsa": {
                "score": dsa_score,
                "max": 20,
                "detail": f"{patterns_mastered} patterns mastered (3+ solved each)",
            },
            "career": {
                "score": career_score,
                "max": 20,
                "detail": f"{target_count} career targets, resume {'reviewed' if resume_score > 0 else 'not reviewed recently'}",
            },
        },
    }
