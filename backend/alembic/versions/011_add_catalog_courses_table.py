"""add catalog_courses table

Revision ID: 011
Revises: 010
Create Date: 2026-07-27 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "catalog_courses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("university", sa.String(255), nullable=False, index=True),
        sa.Column("course_code", sa.String(32), nullable=False, index=True),
        sa.Column("course_name", sa.String(255), nullable=False),
        sa.Column("credits", sa.Float(), nullable=False, server_default="3.0"),
        sa.Column("subject_faculty", sa.String(32), nullable=True),
        sa.Column("prerequisites", JSONB, nullable=False, server_default="[]"),
        sa.Column("gpa_gate", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("university", "course_code", name="uq_catalog_university_course_code"),
    )


def downgrade() -> None:
    op.drop_table("catalog_courses")
