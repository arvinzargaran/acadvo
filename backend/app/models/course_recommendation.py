import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Numeric, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CourseRecommendation(Base):
    __tablename__ = "course_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    semester: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    course_code: Mapped[str] = mapped_column(String(20), nullable=False)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    credits: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False, default=3.0)
    requirement_bucket: Mapped[str | None] = mapped_column(String(255))
    reasoning: Mapped[str | None] = mapped_column(Text)
    career_relevance: Mapped[str | None] = mapped_column(Text)
    prerequisite_notes: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    # What the program's cached requirement rules say about this course counting
    # toward `requirement_bucket` — outcome, certainty, the sentence it was read
    # from, and the source URLs. Stored on the recommendation rather than
    # recomputed for display because the student needs to see the basis that
    # existed when the advice was given, and because "counts toward your degree"
    # must never be shown without the citation and the inferred/stated label that
    # came with it. NULL when no rule covers this course.
    bucket_verdict: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="course_recommendations")
