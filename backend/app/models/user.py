import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    university: Mapped[str | None] = mapped_column(Text)
    program: Mapped[str | None] = mapped_column(Text)
    start_year: Mapped[int | None] = mapped_column(Integer)
    expected_graduation_year: Mapped[int | None] = mapped_column(Integer)
    country: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    career_target: Mapped[str | None] = mapped_column(Text)
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_resume_review: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    weekly_summary: Mapped[dict | None] = mapped_column(JSONB)
    weekly_summary_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    study_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    longest_study_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_study_date: Mapped[date | None] = mapped_column(Date)
    daily_study_goal_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    calendar_token: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    # Per-account login throttling. The IP rate limit on /auth/login does not
    # slow a distributed credential-stuffing run at all (one guess per IP per
    # account); these do. Reset on any successful login.
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    login_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    degree_requirements = relationship("DegreeRequirement", back_populates="user", cascade="all, delete-orphan")
    courses = relationship("Course", back_populates="user", cascade="all, delete-orphan")
    credentials = relationship("Credential", back_populates="user", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    career_targets = relationship("CareerTarget", back_populates="user", cascade="all, delete-orphan")
    timeline_events = relationship("TimelineEvent", back_populates="user", cascade="all, delete-orphan")
    ai_suggestions = relationship("AISuggestion", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    course_recommendations = relationship("CourseRecommendation", back_populates="user", cascade="all, delete-orphan")
    dsa_problems = relationship("DSAProblem", back_populates="user", cascade="all, delete-orphan")
    study_sessions = relationship("StudySession", back_populates="user", cascade="all, delete-orphan")
    verification_tokens = relationship("VerificationToken", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="refresh_tokens")


class VerificationToken(Base):
    """Single-use tokens for password reset and email verification.

    The raw token is emailed to the user; only its SHA-256 hash is stored, so a
    DB leak cannot be used to reset accounts or verify emails.
    """

    __tablename__ = "verification_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)  # 'password_reset' | 'email_verify'
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="verification_tokens")
