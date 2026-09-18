"""Record which university pages a research job should read.

Finding a program's requirements page automatically needs a web search, which
does not fit the free tier's per-request token limit. Reading a page you name
does. So the URL becomes the one input a human supplies — once per program, for
everyone in it — and it lives on the job.

Revision ID: 017
Revises: 016
Create Date: 2026-08-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "program_research_jobs",
        sa.Column(
            "source_urls",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("program_research_jobs", "source_urls")
