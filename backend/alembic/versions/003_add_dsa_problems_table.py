"""add dsa_problems table

Revision ID: 003
Revises: c468a357a4ba
Create Date: 2026-03-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003"
down_revision: Union[str, None] = "c468a357a4ba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dsa_difficulty = sa.Enum("easy", "medium", "hard", name="dsa_difficulty")
    dsa_problem_status = sa.Enum("not_started", "attempted", "solved", name="dsa_problem_status")

    op.create_table(
        "dsa_problems",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("difficulty", dsa_difficulty, nullable=False),
        sa.Column("pattern", sa.String(100), nullable=False),
        sa.Column("status", dsa_problem_status, nullable=False, server_default="not_started"),
        sa.Column("notes", sa.Text),
        sa.Column("leetcode_url", sa.Text),
        sa.Column("solved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_dsa_problems_user_id", "dsa_problems", ["user_id"])
    op.create_index("ix_dsa_problems_pattern", "dsa_problems", ["pattern"])


def downgrade() -> None:
    op.drop_table("dsa_problems")
    sa.Enum(name="dsa_difficulty").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="dsa_problem_status").drop(op.get_bind(), checkfirst=True)
