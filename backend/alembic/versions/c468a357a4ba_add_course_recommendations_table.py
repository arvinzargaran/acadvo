"""add course_recommendations table

Revision ID: c468a357a4ba
Revises: 001
Create Date: 2026-03-22 15:37:20.216341
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c468a357a4ba'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'course_recommendations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('semester', sa.String(50), nullable=False, index=True),
        sa.Column('course_code', sa.String(20), nullable=False),
        sa.Column('course_name', sa.String(255), nullable=False),
        sa.Column('credits', sa.Numeric(4, 2), nullable=False, server_default='3.0'),
        sa.Column('requirement_bucket', sa.String(255)),
        sa.Column('reasoning', sa.Text),
        sa.Column('career_relevance', sa.Text),
        sa.Column('prerequisite_notes', sa.Text),
        sa.Column('priority', sa.String(20), nullable=False, server_default='medium'),
        sa.Column('accepted', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('dismissed', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('course_recommendations')
