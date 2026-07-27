import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

CareerStatus = Literal["researching", "applied", "interviewing", "offer", "rejected"]
TimelineCategory = Literal["deadline", "milestone", "goal", "co_op", "academic"]


# ── CareerTarget schemas ───────────────────────────────────────────


class CareerTargetCreate(BaseModel):
    company_name: str
    role_type: str | None = None
    location: str | None = None
    status: CareerStatus = "researching"
    target_term: str | None = None
    notes: str | None = None


class CareerTargetUpdate(BaseModel):
    company_name: str | None = None
    role_type: str | None = None
    location: str | None = None
    status: CareerStatus | None = None
    target_term: str | None = None
    notes: str | None = None


class CareerTargetResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    company_name: str
    role_type: str | None = None
    location: str | None = None
    status: str
    target_term: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── TimelineEvent schemas ─────────────────────────────────────────


class TimelineEventCreate(BaseModel):
    title: str
    description: str | None = None
    event_date: date
    category: TimelineCategory
    is_hard_deadline: bool = False


class TimelineEventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    event_date: date | None = None
    category: TimelineCategory | None = None
    is_hard_deadline: bool | None = None


class TimelineEventResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str | None = None
    event_date: date
    category: str
    is_hard_deadline: bool
    created_at: datetime

    model_config = {"from_attributes": True}
