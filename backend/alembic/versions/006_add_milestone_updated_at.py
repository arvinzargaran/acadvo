"""add milestone updated_at

Revision ID: 006
Revises: 0514679c4a7f
Create Date: 2026-04-25
"""
from typing import Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "0514679c4a7f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "milestones",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_column("milestones", "updated_at")
