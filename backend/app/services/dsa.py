import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dsa import DSAProblem, DSASettings, Difficulty, ProblemStatus
from app.schemas.dsa import DSAProblemCreate, DSAProblemUpdate, DSASettingsUpdate

DEFAULT_WEEKLY_GOAL = 7


async def list_problems(user_id: uuid.UUID, db: AsyncSession) -> list[DSAProblem]:
    result = await db.execute(
        select(DSAProblem)
        .where(DSAProblem.user_id == user_id)
        .order_by(DSAProblem.created_at.desc())
    )
    return list(result.scalars().all())


async def create_problem(
    user_id: uuid.UUID, data: DSAProblemCreate, db: AsyncSession
) -> DSAProblem:
    problem = DSAProblem(
        user_id=user_id,
        title=data.title,
        difficulty=Difficulty(data.difficulty),
        pattern=data.pattern,
        status=ProblemStatus(data.status),
        notes=data.notes,
        leetcode_url=data.leetcode_url,
    )
    if data.status == "solved":
        problem.solved_at = datetime.now(timezone.utc)
    db.add(problem)
    await db.commit()
    await db.refresh(problem)
    return problem


async def update_problem(
    problem_id: uuid.UUID,
    user_id: uuid.UUID,
    data: DSAProblemUpdate,
    db: AsyncSession,
) -> DSAProblem:
    result = await db.execute(
        select(DSAProblem).where(
            DSAProblem.id == problem_id, DSAProblem.user_id == user_id
        )
    )
    problem = result.scalar_one_or_none()
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "status" and value == "solved" and problem.status != ProblemStatus.solved:
            problem.solved_at = datetime.now(timezone.utc)
        if field == "difficulty":
            value = Difficulty(value)
        elif field == "status":
            value = ProblemStatus(value)
        setattr(problem, field, value)

    await db.commit()
    await db.refresh(problem)
    return problem


async def delete_problem(
    problem_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> None:
    result = await db.execute(
        select(DSAProblem).where(
            DSAProblem.id == problem_id, DSAProblem.user_id == user_id
        )
    )
    problem = result.scalar_one_or_none()
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found")
    await db.delete(problem)
    await db.commit()


async def get_stats(user_id: uuid.UUID, db: AsyncSession) -> dict:
    problems = await list_problems(user_id, db)

    total = len(problems)
    solved = [p for p in problems if p.status == ProblemStatus.solved]
    total_solved = len(solved)

    # Solved by difficulty
    diff_counts: dict[str, int] = {}
    for p in solved:
        diff_counts[p.difficulty.value] = diff_counts.get(p.difficulty.value, 0) + 1
    solved_by_difficulty = [
        {"difficulty": d, "count": c}
        for d, c in sorted(diff_counts.items())
    ]

    # Solved by pattern
    pattern_counts: dict[str, int] = {}
    for p in solved:
        pattern_counts[p.pattern] = pattern_counts.get(p.pattern, 0) + 1
    solved_by_pattern = [
        {"pattern": pat, "count": c}
        for pat, c in sorted(pattern_counts.items(), key=lambda x: -x[1])
    ]

    # Weekly solved (last 7 days).
    #
    # solved_at is normalised before comparing: the column is timestamptz and
    # Postgres hands back an aware datetime, but a naive one — from a driver that
    # does not carry tzinfo, or a row written by a migration — makes this
    # comparison raise TypeError and takes the whole stats endpoint down with it.
    # `authenticate_user` already guards its own timestamp the same way.
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    weekly_solved = 0
    for p in solved:
        solved_at = p.solved_at
        if solved_at is None:
            continue
        if solved_at.tzinfo is None:
            solved_at = solved_at.replace(tzinfo=timezone.utc)
        if solved_at >= week_ago:
            weekly_solved += 1

    return {
        "total_solved": total_solved,
        "total_problems": total,
        "solved_by_difficulty": solved_by_difficulty,
        "solved_by_pattern": solved_by_pattern,
        "weekly_solved": weekly_solved,
    }


async def get_settings(user_id: uuid.UUID, db: AsyncSession) -> dict:
    """Return the user's DSA settings, or a transient default if none stored yet.

    ``is_default`` is True when no row is persisted, which the client uses to
    decide whether to run its one-time localStorage → server migration.
    """
    result = await db.execute(
        select(DSASettings).where(DSASettings.user_id == user_id)
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        return {"weekly_goal": DEFAULT_WEEKLY_GOAL, "is_default": True}
    return {"weekly_goal": settings.weekly_goal, "is_default": False}


async def update_settings(
    user_id: uuid.UUID, data: DSASettingsUpdate, db: AsyncSession
) -> dict:
    """Upsert the user's weekly goal."""
    result = await db.execute(
        select(DSASettings).where(DSASettings.user_id == user_id)
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = DSASettings(user_id=user_id, weekly_goal=data.weekly_goal)
        db.add(settings)
    else:
        settings.weekly_goal = data.weekly_goal
    await db.commit()
    await db.refresh(settings)
    return {"weekly_goal": settings.weekly_goal, "is_default": False}
