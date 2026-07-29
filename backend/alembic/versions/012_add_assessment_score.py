"""add score column to assessments

Revision ID: 012
Revises: 011
Create Date: 2026-07-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("assessments", sa.Column("score", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("assessments", "score")
