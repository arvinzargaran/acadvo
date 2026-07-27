import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Difficulty(str, enum.Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class ProblemStatus(str, enum.Enum):
    not_started = "not_started"
    attempted = "attempted"
    solved = "solved"


class DSAProblem(Base):
    __tablename__ = "dsa_problems"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    difficulty: Mapped[Difficulty] = mapped_column(Enum(Difficulty, name="dsa_difficulty"), nullable=False)
    pattern: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[ProblemStatus] = mapped_column(Enum(ProblemStatus, name="dsa_problem_status"), nullable=False, default=ProblemStatus.not_started)
    notes: Mapped[str | None] = mapped_column(Text)
    leetcode_url: Mapped[str | None] = mapped_column(Text)
    solved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="dsa_problems")


class DSASettings(Base):
    """Per-user DSA preferences (currently just the weekly problem-solving goal).

    One row per user; the row is created lazily on first PUT /dsa/settings. When
    no row exists the API returns a default weekly_goal of 7.
    """

    __tablename__ = "dsa_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    weekly_goal: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User")
