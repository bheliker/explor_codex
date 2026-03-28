"""add poi images bridge

Revision ID: 529620bbf6d0
Revises: ab57fc4b3755
Create Date: 2026-03-27 18:20:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "529620bbf6d0"
down_revision = "ab57fc4b3755"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "poi_images",
        sa.Column("poi", sa.Integer(), nullable=False),
        sa.Column("image", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["poi"], ["points_of_interest.id"]),
        sa.ForeignKeyConstraint(["image"], ["image.id"]),
        sa.PrimaryKeyConstraint("poi", "image"),
    )


def downgrade() -> None:
    op.drop_table("poi_images")
