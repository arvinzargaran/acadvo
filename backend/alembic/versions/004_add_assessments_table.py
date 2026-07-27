"""add assessments table

Revision ID: 004
Revises: c468a357a4ba
Create Date: 2026-03-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    assessment_category = postgresql.ENUM(
        "exam", "assignment", "quiz", "other", name="assessment_category", create_type=False
    )
    assessment_category.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "assessments",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "category",
            postgresql.ENUM("exam", "assignment", "quiz", "other", name="assessment_category", create_type=False),
            nullable=False,
            server_default="other",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assessments_course_id", "assessments", ["course_id"])


def downgrade() -> None:
    op.drop_index("ix_assessments_course_id", table_name="assessments")
    op.drop_table("assessments")
    op.execute("DROP TYPE IF EXISTS assessment_category")
