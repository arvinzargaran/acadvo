import uuid
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field


class StudySessionBase(BaseModel):
    duration_minutes: int = Field(..., gt=0)


class StudySessionCreate(StudySessionBase):
    pass


class StudySessionResponse(StudySessionBase):
    id: uuid.UUID
    user_id: uuid.UUID
    date: date
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StudyStatsResponse(BaseModel):
    current_streak: int
    longest_streak: int
    last_study_date: date | None
    daily_goal_minutes: int
    today_minutes: int
    week_activity: list[int]
