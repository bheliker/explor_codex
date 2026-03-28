"""add route and segment json arrays

Revision ID: 43370fbf4c8d
Revises: 529620bbf6d0
Create Date: 2026-03-27 18:35:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "43370fbf4c8d"
down_revision = "529620bbf6d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("route", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tags", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("elevation_array", sa.JSON(), nullable=True))

    with op.batch_alter_table("segment", schema=None) as batch_op:
        batch_op.add_column(sa.Column("elevation_array", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("tags", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("segment", schema=None) as batch_op:
        batch_op.drop_column("tags")
        batch_op.drop_column("elevation_array")

    with op.batch_alter_table("route", schema=None) as batch_op:
        batch_op.drop_column("elevation_array")
        batch_op.drop_column("tags")
