import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SuggestionType(str, enum.Enum):
    course = "course"
    project = "project"
    career = "career"
    schedule = "schedule"
    risk_flag = "risk_flag"


class RiskSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class AISuggestion(Base):
    __tablename__ = "ai_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"))
    suggestion_type: Mapped[SuggestionType] = mapped_column(Enum(SuggestionType, name="suggestion_type"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[RiskSeverity | None] = mapped_column(Enum(RiskSeverity, name="risk_severity"))
    accepted: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="ai_suggestions")
    conversation = relationship("Conversation", back_populates="ai_suggestions")
