"""Grandfather existing accounts as email-verified.

Migration 014 and earlier recorded `email_verified` but nothing ever read it, so
every account created before this point sits at False regardless of whether the
address was actually confirmed. Now that state-changing requests require the
flag (see app/deps.py require_verified_email), leaving those rows alone would
lock every existing user out of their own data overnight — including anyone who
did click their verification link back when the column was purely decorative.

Marking them verified is the standard grandfathering step: the new rule applies
to accounts created from here on. If you would rather force everyone through
verification instead, drop this migration before deploying and be ready for the
support load.

Revision ID: 015
Revises: 014
"""

from typing import Sequence, Union

from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE users SET email_verified = true WHERE email_verified = false")


def downgrade() -> None:
    # Not reversible: the pre-migration state did not distinguish "never
    # verified" from "verified while the flag was unused", so there is nothing
    # to restore it to. Downgrading leaves the flags as they are.
    pass
