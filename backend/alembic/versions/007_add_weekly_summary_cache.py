"""add weekly summary cache to users

Revision ID: 007
Revises: 006
Create Date: 2026-07-14
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("weekly_summary", JSONB, nullable=True))
    op.add_column(
        "users",
        sa.Column("weekly_summary_generated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "weekly_summary_generated_at")
    op.drop_column("users", "weekly_summary")
