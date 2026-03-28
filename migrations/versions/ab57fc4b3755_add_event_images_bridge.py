"""add event images bridge

Revision ID: ab57fc4b3755
Revises: 54ef7b0af8c1
Create Date: 2026-03-27 18:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ab57fc4b3755"
down_revision = "54ef7b0af8c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_images",
        sa.Column("event", sa.Integer(), nullable=False),
        sa.Column("image", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["event"], ["event.id"]),
        sa.ForeignKeyConstraint(["image"], ["image.id"]),
        sa.PrimaryKeyConstraint("event", "image"),
    )


def downgrade() -> None:
    op.drop_table("event_images")
