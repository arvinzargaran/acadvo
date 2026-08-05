import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.weburl import WebUrl

DSADifficulty = Literal["easy", "medium", "hard"]
DSAProblemStatusType = Literal["not_started", "attempted", "solved"]


class DSAProblemCreate(BaseModel):
    title: str
    difficulty: DSADifficulty
    pattern: str
    status: DSAProblemStatusType = "not_started"
    notes: str | None = None
    leetcode_url: WebUrl = None


class DSAProblemUpdate(BaseModel):
    title: str | None = None
    difficulty: DSADifficulty | None = None
    pattern: str | None = None
    status: DSAProblemStatusType | None = None
    notes: str | None = None
    leetcode_url: WebUrl = None


class DSAProblemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    difficulty: str
    pattern: str
    status: str
    notes: str | None = None
    leetcode_url: WebUrl = None
    solved_at: datetime | None = None
    created_at: datetime


class PatternCount(BaseModel):
    pattern: str
    count: int


class DifficultyCount(BaseModel):
    difficulty: str
    count: int


class DSAStatsResponse(BaseModel):
    total_solved: int
    total_problems: int
    solved_by_difficulty: list[DifficultyCount]
    solved_by_pattern: list[PatternCount]
    weekly_solved: int


class DSASettingsUpdate(BaseModel):
    weekly_goal: int = Field(ge=1, le=100)


class DSASettingsResponse(BaseModel):
    weekly_goal: int
    # True when no settings row is persisted yet and the default is being returned.
    # Lets the client run its one-time localStorage → server migration.
    is_default: bool = False
