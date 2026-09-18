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
    # Same bounds as CourseCreate. Validation that exists only on create is a
    # gap, not a policy: an unbounded credit_value on update skews every GPA and
    # credit total, and an over-length string reaches the DB as an unhandled
    # DataError (a 500) instead of a 422.
    course_code: str | None = Field(default=None, min_length=1, max_length=20)
    course_name: str | None = Field(default=None, min_length=1, max_length=200)
    credit_value: float | None = Field(default=None, ge=0, le=20)
    status: CourseStatusType | None = None
    term: str | None = Field(default=None, max_length=50)
    grade: str | None = Field(default=None, max_length=10)
    requirement_bucket_id: uuid.UUID | None = None
    credential_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


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
    # Additive, optional fields (backward-compatible).
    # prerequisites: list of requirement groups; each group is a list of
    # alternative canonical codes (AND across groups, OR within a group).
    prerequisites: list[list[str]] = Field(default_factory=list)
    # alternatives: other canonical codes that satisfy this same slot
    # (from collapsed "A or B" rows).
    alternatives: list[str] = Field(default_factory=list)
    # prerequisites_raw: verbatim "Notes / Prerequisites" text, if any.
    prerequisites_raw: str | None = None
    # completion_evidence: the verbatim document text backing a "completed"
    # status — a grade, or a column value such as "Passed: True". Only ever set
    # on a completed course. It is what lets a checklist WITHOUT a grade column
    # (York's own BSc checklist records Enrolled/Passed booleans) report real
    # completions, while a blank checklist still reports none.
    completion_evidence: str | None = None
    # gpa_gate: structured minimum-GPA gate, e.g. {"scope": "EECS", "min": 4.5}.
    gpa_gate: dict | None = None


class ParsedDegreeDocument(BaseModel):
    requirements: list[ParsedRequirement]
    courses: list[ParsedCourse]


# ── Catalog Status ───────────────────────────────────────────────────

class CatalogStatusResponse(BaseModel):
    """Whether AI advising for the user's university is grounded in a verified,
    seeded course catalog (``verified``) or running best-effort off the student's
    own uploaded courses. Powers the "Verified vs best-effort" badge in the UI."""

    model_config = ConfigDict(from_attributes=True)

    university: str | None = None
    verified: bool = False
    course_count: int = 0
    last_updated: datetime | None = None
    sources: list[str] = Field(default_factory=list)


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
    score: float | None = Field(default=None, ge=0, le=100)
    category: AssessmentCategoryType = "other"
    notes: str | None = Field(default=None, max_length=2000)


class AssessmentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    due_date: datetime | None = None
    weight: float | None = Field(default=None, ge=0, le=100)
    score: float | None = Field(default=None, ge=0, le=100)
    category: AssessmentCategoryType | None = None
    notes: str | None = Field(default=None, max_length=2000)


class AssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    due_date: datetime | None = None
    weight: float
    score: float | None = None
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


class CourseGradeProjection(BaseModel):
    """Final-grade projection for a course.

    All weights/scores are percentages. ``current_weighted_pct`` is the
    student's average over the graded portion only; ``projected_final_pct``
    extrapolates that average across the remaining (ungraded) weight — i.e. it
    assumes the student maintains their current standing on what's left.
    """

    graded_weight: float
    total_weight: float
    remaining_weight: float
    current_weighted_pct: float | None = None
    projected_final_pct: float | None = None
    projected_letter: str | None = None
    projected_gpa_points: float | None = None
    scale_name: str
    scale_max: float
    # Populated only when a ``target`` is supplied to the projection endpoint.
    target_final_pct: float | None = None
    score_needed_on_remaining: float | None = None
    target_achievable: bool | None = None
    target_already_secured: bool | None = None


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
    gate: float
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


class GPAGoalResponse(BaseModel):
    """Reverse goal projection: the average GPA a student must earn on their
    remaining credits to reach a target cumulative GPA.

    ``needed_average`` = (target*(completed+remaining) - cumulative*completed)
    / remaining, using the completed side from ``calculate_gpa``. It is clamped
    to >= 0 for display, with ``already_met`` flagging the case where the raw
    requirement is <= 0 (the target is already secured regardless of remaining
    work) and ``achievable`` flagging whether it fits under ``scale_max``.
    """

    target: float
    remaining_credits: float
    current_cumulative_gpa: float | None
    total_credits_completed: float
    needed_average: float
    achievable: bool
    already_met: bool
    scale_max: float


class MajorGPAGoalResponse(BaseModel):
    """Reverse goal projection for a subject-subset (major) GPA gate — e.g. the
    average a student must earn on their next N EECS credits to clear York's
    4.50 EECS-major gate. Mirrors :class:`GPAGoalResponse` but the target is the
    program ``gate`` and the completed side comes from ``calculate_major_gpa``."""

    scope: str
    gate: float
    remaining_credits: float
    current_major_gpa: float | None
    major_credits_completed: float
    needed_average: float
    achievable: bool
    already_met: bool
    meets_gate: bool
    scale_max: float
