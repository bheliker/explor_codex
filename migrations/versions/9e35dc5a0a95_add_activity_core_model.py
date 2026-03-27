"""add activity core model

Revision ID: 9e35dc5a0a95
Revises: 65b38dc57c91
Create Date: 2026-03-27 11:20:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9e35dc5a0a95"
down_revision = "65b38dc57c91"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("init_date", sa.DateTime(), nullable=False),
        sa.Column("update_date", sa.DateTime(), nullable=False),
        sa.Column("athlete_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=2048), nullable=True),
        sa.Column("desc", sa.String(length=2048), nullable=True),
        sa.Column("private", sa.Boolean(), nullable=True),
        sa.Column("photo_url", sa.String(length=2048), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("length", sa.Float(), nullable=True),
        sa.Column("elevation_gain", sa.Float(), nullable=True),
        sa.Column("average_speed", sa.Float(), nullable=True),
        sa.Column("max_speed", sa.Float(), nullable=True),
        sa.Column("moving_time", sa.Float(), nullable=True),
        sa.Column("start_date", sa.DateTime(), nullable=False),
        sa.Column("end_date", sa.DateTime(), nullable=False),
        sa.Column("total_elevation_gain", sa.Float(), nullable=True),
        sa.Column("elev_high", sa.Float(), nullable=True),
        sa.Column("elev_low", sa.Float(), nullable=True),
        sa.Column("type", sa.String(length=128), nullable=True),
        sa.Column("subtype", sa.String(length=128), nullable=True),
        sa.Column("src", sa.String(length=128), nullable=True),
        sa.Column("src_id", sa.String(length=128), nullable=True),
        sa.Column("start_longitude", sa.Float(), nullable=True),
        sa.Column("start_latitude", sa.Float(), nullable=True),
        sa.Column("end_longitude", sa.Float(), nullable=True),
        sa.Column("end_latitude", sa.Float(), nullable=True),
        sa.Column("route_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["athlete_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["route_id"], ["route.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("activity")
