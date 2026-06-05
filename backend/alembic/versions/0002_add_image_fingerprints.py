"""add sha256 + phash256 image fingerprints

Adds the stricter image-fingerprint columns to content_registrations:
  - sha256   : exact raw-bytes hash (byte-for-byte "verified" tier)
  - phash256 : 256-bit perceptual hash (hash_size=16)

Guarded with the dialect inspector so it is safe regardless of starting point:
a fresh DB already has the columns (baseline create_all used the current ORM),
and a DB where the columns were added out-of-band is left untouched.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "content_registrations"
INDEX = "ix_content_registrations_sha256"


def _columns(bind) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(TABLE)}


def _indexes(bind) -> set[str]:
    return {i["name"] for i in sa.inspect(bind).get_indexes(TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _columns(bind)
    if "sha256" not in cols:
        op.add_column(TABLE, sa.Column("sha256", sa.String(), nullable=True))
    if "phash256" not in cols:
        op.add_column(TABLE, sa.Column("phash256", sa.String(), nullable=True))
    if INDEX not in _indexes(bind):
        op.create_index(INDEX, TABLE, ["sha256"])


def downgrade() -> None:
    bind = op.get_bind()
    if INDEX in _indexes(bind):
        op.drop_index(INDEX, table_name=TABLE)
    cols = _columns(bind)
    if "phash256" in cols:
        op.drop_column(TABLE, "phash256")
    if "sha256" in cols:
        op.drop_column(TABLE, "sha256")
