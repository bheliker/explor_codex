"""add segment core model

Revision ID: 65b38dc57c91
Revises: 2925e18f3215
Create Date: 2026-03-27 10:30:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "65b38dc57c91"
down_revision = "2925e18f3215"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "segment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("init_date", sa.DateTime(), nullable=False),
        sa.Column("update_date", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(length=2048), nullable=True),
        sa.Column("desc", sa.String(length=2048), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("length", sa.Float(), nullable=True),
        sa.Column("elevation_gain", sa.Float(), nullable=True),
        sa.Column("elevation_loss", sa.Float(), nullable=True),
        sa.Column("elev_high", sa.Float(), nullable=True),
        sa.Column("elev_low", sa.Float(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("grade", sa.Float(), nullable=True),
        sa.Column("type", sa.String(length=128), nullable=True),
        sa.Column("subtype", sa.String(length=128), nullable=True),
        sa.Column("src", sa.String(length=128), nullable=True),
        sa.Column("src_id", sa.String(length=128), nullable=True),
        sa.Column("src_url", sa.String(length=2048), nullable=True),
        sa.Column("start_longitude", sa.Float(), nullable=True),
        sa.Column("start_latitude", sa.Float(), nullable=True),
        sa.Column("end_longitude", sa.Float(), nullable=True),
        sa.Column("end_latitude", sa.Float(), nullable=True),
        sa.Column("track_hash", sa.String(length=32), nullable=True),
        sa.Column("track_maxspeed", sa.Float(), nullable=True),
        sa.Column("record_date", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("track_hash"),
    )
    op.create_index(op.f("ix_segment_track_hash"), "segment", ["track_hash"], unique=True)
    op.create_table(
        "route_segments",
        sa.Column("routes", sa.Integer(), nullable=False),
        sa.Column("segments", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["routes"], ["route.id"]),
        sa.ForeignKeyConstraint(["segments"], ["segment.id"]),
        sa.PrimaryKeyConstraint("routes", "segments"),
    )


def downgrade() -> None:
    op.drop_table("route_segments")
    op.drop_index(op.f("ix_segment_track_hash"), table_name="segment")
    op.drop_table("segment")
