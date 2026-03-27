"""add group routes bridge

Revision ID: 0fb577fba923
Revises: 8fdd5032cd76
Create Date: 2026-03-27 12:40:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0fb577fba923"
down_revision = "8fdd5032cd76"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "group_routes",
        sa.Column("group", sa.Integer(), nullable=False),
        sa.Column("route", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["group"], ["group.id"]),
        sa.ForeignKeyConstraint(["route"], ["route.id"]),
        sa.PrimaryKeyConstraint("group", "route"),
    )


def downgrade() -> None:
    op.drop_table("group_routes")
