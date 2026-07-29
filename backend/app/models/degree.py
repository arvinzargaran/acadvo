import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CourseStatus(str, enum.Enum):
    completed = "completed"
    in_progress = "in_progress"
    planned = "planned"
    not_scheduled = "not_scheduled"


class AssessmentCategory(str, enum.Enum):
    exam = "exam"
    assignment = "assignment"
    quiz = "quiz"
    other = "other"


class DegreeRequirement(Base):
    __tablename__ = "degree_requirements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    bucket_name: Mapped[str] = mapped_column(Text, nullable=False)
    credits_required: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    user = relationship("User", back_populates="degree_requirements")
    courses = relationship("Course", back_populates="requirement_bucket", cascade="all, delete-orphan")


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    total_credits_required: Mapped[float | None] = mapped_column(Numeric(5, 2))
    notes: Mapped[str | None] = mapped_column(Text)

    user = relationship("User", back_populates="credentials")
    courses = relationship("Course", back_populates="credential")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_code: Mapped[str] = mapped_column(String(20), nullable=False)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    credit_value: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    status: Mapped[CourseStatus] = mapped_column(Enum(CourseStatus, name="course_status"), nullable=False, default=CourseStatus.not_scheduled, index=True)
    term: Mapped[str | None] = mapped_column(String(50))
    grade: Mapped[str | None] = mapped_column(String(10))
    requirement_bucket_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("degree_requirements.id", ondelete="SET NULL"), index=True)
    credential_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("credentials.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="courses")
    requirement_bucket = relationship("DegreeRequirement", back_populates="courses")
    credential = relationship("Credential", back_populates="courses")
    assessments = relationship("Assessment", back_populates="course", cascade="all, delete-orphan")


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score: Mapped[float | None] = mapped_column(Float)  # percent (0-100) the student earned, null until graded
    category: Mapped[AssessmentCategory] = mapped_column(Enum(AssessmentCategory, name="assessment_category"), nullable=False, default=AssessmentCategory.other)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    course = relationship("Course", back_populates="assessments")
