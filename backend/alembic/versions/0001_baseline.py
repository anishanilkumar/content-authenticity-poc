"""baseline schema (creators, content_registrations)

Adopts Alembic on top of the schema previously created by
`Base.metadata.create_all`. Uses create_all (checkfirst=True), so this is a
no-op on the existing production database and creates the full schema on a fresh
one. The incremental column additions live in later revisions.

Revision ID: 0001
Revises:
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op

# database.py / models.py are importable via prepend_sys_path = backend.
from database import Base
import models  # noqa: F401  (registers tables on Base.metadata)

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # checkfirst=True: only creates tables that don't already exist.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
