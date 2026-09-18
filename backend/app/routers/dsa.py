import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.limiter import CRUD_WRITE_LIMIT, limiter, user_or_ip_key
from app.models.user import User
from app.schemas.dsa import (
    DSAProblemCreate,
    DSAProblemResponse,
    DSAProblemUpdate,
    DSASettingsResponse,
    DSASettingsUpdate,
    DSAStatsResponse,
)
from app.services import dsa as dsa_service

router = APIRouter()


@router.get("/problems", response_model=list[DSAProblemResponse])
async def list_problems(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await dsa_service.list_problems(user.id, db)


@router.post("/problems", response_model=DSAProblemResponse, status_code=201)
@limiter.limit(CRUD_WRITE_LIMIT, key_func=user_or_ip_key)
async def create_problem(
    request: Request,
    data: DSAProblemCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await dsa_service.create_problem(user.id, data, db)


@router.put("/problems/{problem_id}", response_model=DSAProblemResponse)
@limiter.limit(CRUD_WRITE_LIMIT, key_func=user_or_ip_key)
async def update_problem(
    request: Request,
    problem_id: uuid.UUID,
    data: DSAProblemUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await dsa_service.update_problem(problem_id, user.id, data, db)


@router.delete("/problems/{problem_id}", status_code=204)
@limiter.limit(CRUD_WRITE_LIMIT, key_func=user_or_ip_key)
async def delete_problem(
    request: Request,
    problem_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await dsa_service.delete_problem(problem_id, user.id, db)


@router.get("/stats", response_model=DSAStatsResponse)
async def get_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await dsa_service.get_stats(user.id, db)


@router.get("/settings", response_model=DSASettingsResponse)
async def get_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await dsa_service.get_settings(user.id, db)


@router.put("/settings", response_model=DSASettingsResponse)
@limiter.limit(CRUD_WRITE_LIMIT, key_func=user_or_ip_key)
async def update_settings(
    request: Request,
    data: DSASettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await dsa_service.update_settings(user.id, data, db)
