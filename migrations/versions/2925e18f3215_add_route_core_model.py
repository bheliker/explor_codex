"""add route core model

Revision ID: 2925e18f3215
Revises: 4b9929e64ce0
Create Date: 2026-03-27 09:30:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2925e18f3215"
down_revision = "4b9929e64ce0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "route",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("init_date", sa.DateTime(), nullable=False),
        sa.Column("update_date", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(length=2048), nullable=True),
        sa.Column("desc", sa.String(length=2048), nullable=True),
        sa.Column("athlete_id", sa.Integer(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("private", sa.Boolean(), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("length", sa.Float(), nullable=True),
        sa.Column("elevation_gain", sa.Float(), nullable=True),
        sa.Column("type", sa.String(length=128), nullable=True),
        sa.Column("subtype", sa.String(length=128), nullable=True),
        sa.Column("grade", sa.Float(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("src", sa.String(length=128), nullable=True),
        sa.Column("src_id", sa.String(length=128), nullable=True),
        sa.Column("start_longitude", sa.Float(), nullable=True),
        sa.Column("start_latitude", sa.Float(), nullable=True),
        sa.Column("end_longitude", sa.Float(), nullable=True),
        sa.Column("end_latitude", sa.Float(), nullable=True),
        sa.Column("map_thumbnail", sa.String(length=2048), nullable=True),
        sa.Column("city", sa.String(length=256), nullable=True),
        sa.Column("state", sa.String(length=256), nullable=True),
        sa.Column("country", sa.String(length=256), nullable=True),
        sa.Column("address", sa.String(length=2048), nullable=True),
        sa.ForeignKeyConstraint(["creator_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("route")
