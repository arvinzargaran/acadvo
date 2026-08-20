"""Cached, AI-extracted degree requirement rules — and the jobs that produce them.

The problem these tables solve
------------------------------
``CatalogCourse`` can say what ``LE/EECS 2030`` is. It cannot say what satisfies
"Non-Science General Education", because that requirement is not a list of
courses — it is a *rule*: "6.00 credits in AP/HUMA, 6.00 in AP/SOSC, 6.00 in
SC/NATS", minus an exclusion list. Hundreds of courses qualify. No document
enumerates them and none ever will.

That knowledge lives in prose on each university's public pages, and it differs
per school. So it is extracted by a model that can read those pages — and then
**stored**, which is the whole design:

* Not hand-written rules. Those do not scale past the first school.
* Not a fresh model call per question either. Cost would grow linearly forever,
  two students in the same program would get different answers, and a mistake
  would be unfixable because nothing recorded the reasoning.

The first student in a program pays for the research once; every student after
them gets the same answer instantly, and every answer carries the URLs it came
from, so a wrong rule can be found and corrected rather than re-hallucinated.

Honesty columns
---------------
``basis`` and ``source_urls`` are not metadata, they are the product. A rule the
model read plainly off a calendar page and a rule it worked out from surrounding
prose are both useful, but a student must never be told the second one as if it
were the first: "this counts toward your degree" is the one error in this app
that fails silently and surfaces a year later, too late to fix.

``stated_codes`` and ``excluded_codes`` are kept as separate columns for the same
reason the checklist parser splits on "will not count towards": **an exclusion
list is not an option list.** Collapsing them would have the advisor recommend
precisely the courses the requirement rules out.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# How a rule came to be known. Surfaced to the student verbatim, so the wording
# matters: `stated` means the source page says it, `inferred` means the model
# concluded it from the source page.
BASIS_STATED = "stated"
BASIS_INFERRED = "inferred"
RULE_BASES = frozenset({BASIS_STATED, BASIS_INFERRED})

# Research job lifecycle.
JOB_PENDING = "pending"
JOB_RUNNING = "running"
JOB_SUCCEEDED = "succeeded"
JOB_FAILED = "failed"
JOB_STATUSES = frozenset({JOB_PENDING, JOB_RUNNING, JOB_SUCCEEDED, JOB_FAILED})


class RequirementRule(Base):
    """One requirement bucket of one program, expressed as a matchable rule.

    Column notes:
    - ``allowed_subjects`` holds subject prefixes as the university writes them,
      e.g. ``["AP/HUMA", "AP/SOSC", "SC/NATS"]`` or ``["CMPT"]``. A course
      matches when its subject (and faculty prefix, when the rule gives one)
      matches an entry.
    - ``level_floor`` / ``level_ceiling`` bound the course number, e.g. 2000
      means "2000-level or above". ``None`` means unbounded.
    - ``stated_codes`` are codes the source page explicitly names as satisfying
      this bucket. They upgrade a match from *inferred* to *stated*; they never
      introduce a course that is not already in the catalog.
    - ``excluded_codes`` / ``excluded_subjects`` come from the "will not count
      towards this requirement" sentences. A hit here is a hard no.
    - ``source_urls`` is a list of ``{"uri", "title", "domain"}`` — the pages the
      model actually retrieved, taken from the provider's grounding metadata
      rather than from anything the model wrote.
    """

    __tablename__ = "requirement_rules"
    __table_args__ = (
        UniqueConstraint(
            "university", "program", "bucket_name", name="uq_requirement_rule_scope"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    university: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    program: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    bucket_name: Mapped[str] = mapped_column(String(255), nullable=False)

    credits_required: Mapped[float | None] = mapped_column(Float, nullable=True)
    allowed_subjects: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    level_floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    level_ceiling: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stated_codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    excluded_codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    excluded_subjects: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # The sentence(s) the rule was read from, quoted. Shown to the student
    # alongside the verdict so they can judge it themselves.
    source_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    basis: Mapped[str] = mapped_column(String(16), nullable=False, default=BASIS_INFERRED)
    source_urls: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    extracted_by: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class ProgramResearchJob(Base):
    """One research run per ``(university, program)`` — queue, lock and audit log.

    Persisted rather than held in memory for three reasons: it dedupes
    concurrent first-students in the same program down to a single run, it lets a
    restarted process pick up work it never finished, and a failed run leaves a
    readable ``last_error`` instead of vanishing into a log line.
    """

    __tablename__ = "program_research_jobs"
    __table_args__ = (
        UniqueConstraint("university", "program", name="uq_research_job_scope"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    university: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    program: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # The university pages to read for this program, supplied by a student (see
    # the /program-rules/research endpoint) rather than found by the model.
    # Discovery would need Google Search grounding, which is a billed feature and
    # returns 429 on the free tier — so the URL is the one piece of the job a
    # human provides, once, for everyone in the program.
    source_urls: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=JOB_PENDING, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rules_extracted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
