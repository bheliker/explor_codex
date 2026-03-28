"""add route and segment geometry payloads

Revision ID: 20c2164420a2
Revises: 2f9c7733d6df
Create Date: 2026-03-27 13:45:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20c2164420a2"
down_revision = "2f9c7733d6df"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("route", schema=None) as batch_op:
        batch_op.add_column(sa.Column("summary_polyline", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("full_track", sa.Text(), nullable=True))

    with op.batch_alter_table("segment", schema=None) as batch_op:
        batch_op.add_column(sa.Column("summary_polyline", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("full_track", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("segment", schema=None) as batch_op:
        batch_op.drop_column("full_track")
        batch_op.drop_column("summary_polyline")

    with op.batch_alter_table("route", schema=None) as batch_op:
        batch_op.drop_column("full_track")
        batch_op.drop_column("summary_polyline")
