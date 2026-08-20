"""Cached AI-researched requirement rules, their research jobs, and the verdict
column that carries one onto a recommendation.

Requirement buckets ("6.00 credits in AP/HUMA") are rules, not course lists, and
they live as prose on each university's public pages. `requirement_rules` stores
what was extracted from those pages once per program, with the URLs it was read
from and whether it was read plainly or concluded; `program_research_jobs` is the
queue, cross-process lock and audit log for the extraction runs.

Revision ID: 016
Revises: 015
Create Date: 2026-08-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "requirement_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("university", sa.String(length=255), nullable=False),
        sa.Column("program", sa.String(length=255), nullable=False),
        sa.Column("bucket_name", sa.String(length=255), nullable=False),
        sa.Column("credits_required", sa.Float(), nullable=True),
        sa.Column(
            "allowed_subjects",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("level_floor", sa.Integer(), nullable=True),
        sa.Column("level_ceiling", sa.Integer(), nullable=True),
        sa.Column(
            "stated_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "excluded_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "excluded_subjects",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("source_quote", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "basis", sa.String(length=16), nullable=False, server_default="inferred"
        ),
        sa.Column(
            "source_urls",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "extracted_by", sa.String(length=64), nullable=False, server_default=""
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "university", "program", "bucket_name", name="uq_requirement_rule_scope"
        ),
    )
    op.create_index(
        "ix_requirement_rules_university", "requirement_rules", ["university"]
    )
    op.create_index("ix_requirement_rules_program", "requirement_rules", ["program"])

    op.create_table(
        "program_research_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("university", sa.String(length=255), nullable=False),
        sa.Column("program", sa.String(length=255), nullable=False),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="pending"
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rules_extracted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("university", "program", name="uq_research_job_scope"),
    )
    op.create_index(
        "ix_program_research_jobs_university", "program_research_jobs", ["university"]
    )
    op.create_index(
        "ix_program_research_jobs_program", "program_research_jobs", ["program"]
    )
    op.create_index(
        "ix_program_research_jobs_status", "program_research_jobs", ["status"]
    )

    # Nullable with no default: NULL means "no rule covers this course", which is
    # a real and common answer, not a missing value to be backfilled.
    op.add_column(
        "course_recommendations",
        sa.Column(
            "bucket_verdict", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("course_recommendations", "bucket_verdict")
    op.drop_index("ix_program_research_jobs_status", table_name="program_research_jobs")
    op.drop_index("ix_program_research_jobs_program", table_name="program_research_jobs")
    op.drop_index(
        "ix_program_research_jobs_university", table_name="program_research_jobs"
    )
    op.drop_table("program_research_jobs")
    op.drop_index("ix_requirement_rules_program", table_name="requirement_rules")
    op.drop_index("ix_requirement_rules_university", table_name="requirement_rules")
    op.drop_table("requirement_rules")
