import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CatalogCourse(Base):
    """Canonical, university-wide course catalog entry.

    Unlike ``Course`` (which is a *student's* copy of a course, scoped to a
    user), a ``CatalogCourse`` is the authoritative record for a course at a
    given university: its canonical code, name, credit value, prerequisites and
    any GPA gate. Other services read these rows to check whether a code exists,
    look up its canonical name/credits, and evaluate prerequisite eligibility.

    Column notes:
    - ``course_code`` is the canonical, faculty-prefixed form, e.g.
      ``"LE/EECS 2101"``. Uniqueness is ``(university, course_code)``.
    - ``prerequisites`` is a JSON list of "requirement groups". Each group is a
      list of alternative canonical codes; ALL groups must be satisfied (AND),
      and any one code within a group satisfies it (OR). ``[]`` means no
      prerequisites. Example (needs 1019 AND (2030)): ``[["LE/EECS 1019"],
      ["LE/EECS 2030"]]``. An "A or B" prerequisite is a single group with two
      codes: ``[["LE/EECS 1012", "LE/EECS 1015"]]``.
    - ``gpa_gate`` is nullable JSON describing a minimum-GPA gate, e.g.
      ``{"scope": "EECS", "min": 4.50}``. ``None`` means no gate.
    """

    __tablename__ = "catalog_courses"
    __table_args__ = (
        UniqueConstraint("university", "course_code", name="uq_catalog_university_course_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    university: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    course_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    credits: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    subject_faculty: Mapped[str | None] = mapped_column(String(32))
    prerequisites: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    gpa_gate: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Provenance: how this row was populated, e.g. "manual" (hand-authored) or an
    # ingestion adapter id like "sfu_course_outlines". Together with updated_at this
    # is the "verified as of" signal that keeps the catalog honest.
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual", server_default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
