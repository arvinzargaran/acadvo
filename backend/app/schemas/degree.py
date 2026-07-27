import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CourseStatusType = Literal["completed", "in_progress", "planned", "not_scheduled"]
AssessmentCategoryType = Literal["exam", "assignment", "quiz", "other"]


# ── Degree Requirements ──────────────────────────────────────────────

class DegreeRequirementCreate(BaseModel):
    bucket_name: str = Field(min_length=1, max_length=100)
    credits_required: float = Field(ge=0, le=500)
    description: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class DegreeRequirementUpdate(BaseModel):
    bucket_name: str | None = Field(default=None, min_length=1, max_length=100)
    credits_required: float | None = Field(default=None, ge=0, le=500)
    description: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class DegreeRequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    bucket_name: str
    credits_required: float
    description: str | None = None
    notes: str | None = None


# ── Courses ──────────────────────────────────────────────────────────

class CourseCreate(BaseModel):
    course_code: str = Field(min_length=1, max_length=20)
    course_name: str = Field(min_length=1, max_length=200)
    credit_value: float = Field(ge=0, le=20)
    status: CourseStatusType = "not_scheduled"
    term: str | None = Field(default=None, max_length=50)
    grade: str | None = Field(default=None, max_length=10)
    requirement_bucket_id: uuid.UUID | None = None
    credential_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class CourseUpdate(BaseModel):
    course_code: str | None = None
    course_name: str | None = None
    credit_value: float | None = None
    status: CourseStatusType | None = None
    term: str | None = None
    grade: str | None = None
    requirement_bucket_id: uuid.UUID | None = None
    credential_id: uuid.UUID | None = None
    notes: str | None = None


class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    course_code: str
    course_name: str
    credit_value: float
    status: str
    term: str | None = None
    grade: str | None = None
    requirement_bucket_id: uuid.UUID | None = None
    credential_id: uuid.UUID | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


# ── Credentials ──────────────────────────────────────────────────────

class CredentialCreate(BaseModel):
    name: str
    description: str | None = None
    total_credits_required: float | None = None
    notes: str | None = None


class CredentialUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    total_credits_required: float | None = None
    notes: str | None = None


class CredentialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None = None
    total_credits_required: float | None = None
    notes: str | None = None


# ── Degree Summary ───────────────────────────────────────────────────

# ── Parsed Document ──────────────────────────────────────────────────

class ParsedRequirement(BaseModel):
    bucket_name: str = ""
    credits_required: float = 0.0
    description: str | None = None


class ParsedCourse(BaseModel):
    course_code: str = ""
    course_name: str = ""
    credit_value: float = 0.0
    requirement_bucket: str | None = None
    term: str | None = None
    status: CourseStatusType = "not_scheduled"
    grade: str | None = None


class ParsedDegreeDocument(BaseModel):
    requirements: list[ParsedRequirement]
    courses: list[ParsedCourse]


# ── Degree Summary ───────────────────────────────────────────────────

class DegreeSummaryBucket(BaseModel):
    bucket_name: str
    credits_required: float
    credits_completed: float
    credits_remaining: float
    percentage: float
    at_risk: bool


class DegreeSummaryResponse(BaseModel):
    buckets: list[DegreeSummaryBucket]
    total_credits_required: float
    total_credits_completed: float
    overall_percentage: float


# ── Assessments ─────────────────────────────────────────────────────

class AssessmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    due_date: datetime | None = None
    weight: float = Field(default=0.0, ge=0, le=100)
    category: AssessmentCategoryType = "other"
    notes: str | None = Field(default=None, max_length=2000)


class AssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    due_date: datetime | None = None
    weight: float
    category: str
    notes: str | None = None
    created_at: datetime


class ParsedAssessment(BaseModel):
    title: str = ""
    due_date: str | None = None
    weight: float = 0.0
    category: str = "other"


class ParsedSyllabus(BaseModel):
    assessments: list[ParsedAssessment]


# ── GPA ─────────────────────────────────────────────────────────────

class TermGPA(BaseModel):
    term: str
    gpa: float
    credits: float
    course_count: int


class MajorGPA(BaseModel):
    scope: str
    gpa: float | None
    credits: float
    meets_gate: bool


class GPAResponse(BaseModel):
    cumulative_gpa: float | None
    term_gpas: list[TermGPA]
    total_credits_completed: float
    graded_course_count: int
    highest_term: TermGPA | None = None
    lowest_term: TermGPA | None = None
    scale_max: float
    scale_name: str
    using_fallback: bool
    major_gpas: list[MajorGPA] = []
