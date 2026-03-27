"""add point of interest model

Revision ID: 4b9929e64ce0
Revises: ba5657ad5048
Create Date: 2026-03-26 17:30:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4b9929e64ce0"
down_revision = "ba5657ad5048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "points_of_interest",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=128), nullable=True),
        sa.Column("subtype", sa.String(length=128), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("description", sa.String(length=2048), nullable=True),
        sa.Column("date_created", sa.DateTime(), nullable=False),
        sa.Column("date_updated", sa.DateTime(), nullable=False),
        sa.Column("icon", sa.String(length=256), nullable=True),
        sa.ForeignKeyConstraint(["owner"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("points_of_interest")
