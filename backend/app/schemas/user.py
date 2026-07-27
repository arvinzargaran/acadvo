import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    university: str | None = None
    program: str | None = None
    start_year: int | None = None
    expected_graduation_year: int | None = None
    country: str | None = None
    city: str | None = None
    career_target: str | None = None
    onboarding_complete: bool
    email_verified: bool
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    university: str | None = Field(default=None, max_length=200)
    program: str | None = Field(default=None, max_length=200)
    start_year: int | None = Field(default=None, ge=1900, le=2100)
    expected_graduation_year: int | None = Field(default=None, ge=1900, le=2100)
    country: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    career_target: str | None = Field(default=None, max_length=200)
    onboarding_complete: bool | None = None
