"""add calendar_token to users

Revision ID: 010
Revises: 009
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("calendar_token", sa.String(64), nullable=True))
    op.create_index("ix_users_calendar_token", "users", ["calendar_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_calendar_token", table_name="users")
    op.drop_column("users", "calendar_token")
