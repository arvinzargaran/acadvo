"""Record terms acceptance, and index the credential foreign key.

Two unrelated small changes in one revision because they landed together.

The terms columns are a record, not a control: the published terms assert that
a registrant accepted them and confirmed an age minimum, and until now nothing
stored whether any given account ever did, or which version it saw. Both are
nullable and are NOT backfilled — every row that predates this genuinely never
accepted anything, and stamping them would fabricate a legal record, which is
worse than having none.

`courses.credential_id` is an `ON DELETE SET NULL` foreign key with no index,
unlike its sibling `requirement_bucket_id`, so deleting one credential scanned
every course row in the table.

Revision ID: 018
Revises: 017
Create Date: 2026-08-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("users", sa.Column("terms_version", sa.String(length=32), nullable=True))
    op.create_index("ix_courses_credential_id", "courses", ["credential_id"])


def downgrade() -> None:
    op.drop_index("ix_courses_credential_id", table_name="courses")
    op.drop_column("users", "terms_version")
    op.drop_column("users", "terms_accepted_at")
