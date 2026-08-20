import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CourseRecommendationCreate(BaseModel):
    semester: str
    course_code: str
    course_name: str
    credits: float = 3.0
    requirement_bucket: str | None = None
    reasoning: str | None = None
    career_relevance: str | None = None
    prerequisite_notes: str | None = None
    priority: str = "medium"


class CourseRecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    semester: str
    course_code: str
    course_name: str
    credits: float
    requirement_bucket: str | None = None
    reasoning: str | None = None
    career_relevance: str | None = None
    prerequisite_notes: str | None = None
    priority: str
    accepted: bool
    dismissed: bool
    created_at: datetime
    # See CourseRecommendation.bucket_verdict. Carries `label`, which is the only
    # string a UI should render for "does this count?" — the hedging for an
    # inferred verdict is baked into it.
    bucket_verdict: dict | None = None


class CourseSearchResult(BaseModel):
    course_code: str
    course_name: str
    credits: float = 3.0
    description: str | None = None
    requirement_bucket: str | None = None
    in_plan: bool = False
    eligible: bool = True
    blocked_reason: str | None = None
    bucket_verdict: dict | None = None


class CourseSearchResponse(BaseModel):
    results: list[CourseSearchResult]
    query: str


class RecommendationRequest(BaseModel):
    semester: str
    goal: str = "both"  # "degree_requirement" | "career" | "both"
    requirement_bucket: str | None = None
