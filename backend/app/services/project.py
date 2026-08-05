import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Milestone, Project
from app.schemas.project import MilestoneCreate, MilestoneUpdate, ProjectCreate, ProjectUpdate


# ── Projects ───────────────────────────────────────────────────────


async def list_projects(user_id: uuid.UUID, db: AsyncSession) -> list[Project]:
    result = await db.execute(
        select(Project)
        .where(Project.user_id == user_id)
        .options(selectinload(Project.milestones))
        .order_by(Project.priority)
    )
    return list(result.scalars().all())


async def get_project(project_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.milestones))
    )
    project = result.scalar_one_or_none()
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def create_project(user_id: uuid.UUID, data: ProjectCreate, db: AsyncSession) -> Project:
    project = Project(
        user_id=user_id,
        name=data.name,
        description=data.description,
        priority=data.priority,
        status=data.status,
        tech_stack=data.tech_stack,
        repo_url=data.repo_url,
        live_url=data.live_url,
        demo_url=data.demo_url,
        hard_deadline=data.hard_deadline,
        product_framing=data.product_framing,
    )
    db.add(project)
    await db.flush()

    if data.milestones:
        for m in data.milestones:
            milestone = Milestone(
                project_id=project.id,
                title=m.title,
                description=m.description,
                target_date=m.target_date,
                order_index=m.order_index,
            )
            db.add(milestone)

    await db.commit()
    await db.refresh(project)
    # Reload with milestones
    return await get_project(project.id, user_id, db)


async def update_project(
    project_id: uuid.UUID, user_id: uuid.UUID, data: ProjectUpdate, db: AsyncSession
) -> Project:
    project = await get_project(project_id, user_id, db)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(project_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> None:
    project = await get_project(project_id, user_id, db)
    await db.delete(project)
    await db.commit()


# ── Milestones ─────────────────────────────────────────────────────


async def create_milestone(
    project_id: uuid.UUID, user_id: uuid.UUID, data: MilestoneCreate, db: AsyncSession
) -> Milestone:
    # Ownership is checked here, not (only) in the router. Every sibling
    # operation enforces it inside the service; leaving this one to its caller
    # means the next caller added is an IDOR by default.
    await get_project(project_id, user_id, db)

    milestone = Milestone(
        project_id=project_id,
        title=data.title,
        description=data.description,
        target_date=data.target_date,
        order_index=data.order_index,
    )
    db.add(milestone)
    await db.commit()
    await db.refresh(milestone)
    return milestone


async def _get_owned_milestone(
    milestone_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> Milestone:
    result = await db.execute(
        select(Milestone)
        .join(Project, Milestone.project_id == Project.id)
        .where(Milestone.id == milestone_id, Project.user_id == user_id)
    )
    milestone = result.scalar_one_or_none()
    if milestone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
    return milestone


async def update_milestone(
    milestone_id: uuid.UUID, user_id: uuid.UUID, data: MilestoneUpdate, db: AsyncSession
) -> Milestone:
    milestone = await _get_owned_milestone(milestone_id, user_id, db)

    update_data = data.model_dump(exclude_unset=True)

    # Auto-set completed_at when status changes to "complete"
    if update_data.get("status") == "complete":
        update_data["completed_at"] = datetime.now(timezone.utc)

    for field, value in update_data.items():
        setattr(milestone, field, value)

    await db.commit()
    await db.refresh(milestone)
    return milestone


async def delete_milestone(milestone_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> None:
    milestone = await _get_owned_milestone(milestone_id, user_id, db)
    await db.delete(milestone)
    await db.commit()
