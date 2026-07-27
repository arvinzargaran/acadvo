import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

ProjectStatus = Literal["not_started", "in_progress", "deployed", "interview_ready"]
MilestoneStatus = Literal["pending", "in_progress", "complete", "overdue"]

# ── Milestone schemas ──────────────────────────────────────────────


class MilestoneCreate(BaseModel):
    title: str
    description: str | None = None
    target_date: date | None = None
    order_index: int


class MilestoneUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    target_date: date | None = None
    status: MilestoneStatus | None = None
    order_index: int | None = None


class MilestoneResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None = None
    target_date: date | None = None
    completed_at: datetime | None = None
    status: str
    order_index: int
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Project schemas ────────────────────────────────────────────────


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    priority: int = Field(ge=1, le=3)
    status: ProjectStatus = "not_started"
    tech_stack: str | None = None
    repo_url: str | None = None
    live_url: str | None = None
    demo_url: str | None = None
    hard_deadline: date | None = None
    product_framing: str | None = None
    milestones: list[MilestoneCreate] | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    priority: int | None = Field(default=None, ge=1, le=3)
    status: ProjectStatus | None = None
    tech_stack: str | None = None
    repo_url: str | None = None
    live_url: str | None = None
    demo_url: str | None = None
    hard_deadline: date | None = None
    product_framing: str | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None = None
    priority: int
    status: str
    tech_stack: str | None = None
    repo_url: str | None = None
    live_url: str | None = None
    demo_url: str | None = None
    hard_deadline: date | None = None
    product_framing: str | None = None
    created_at: datetime
    updated_at: datetime
    milestones: list[MilestoneResponse] = []

    model_config = {"from_attributes": True}
