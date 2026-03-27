"""add event route and activity links

Revision ID: 8fdd5032cd76
Revises: 9e35dc5a0a95
Create Date: 2026-03-27 12:05:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "8fdd5032cd76"
down_revision = "9e35dc5a0a95"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("event", schema=None) as batch_op:
        batch_op.add_column(sa.Column("route_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_event_route_id", "route", ["route_id"], ["id"])

    with op.batch_alter_table("event", schema=None) as batch_op:
        batch_op.add_column(sa.Column("activity_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_event_activity_id", "activity", ["activity_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("event", schema=None) as batch_op:
        batch_op.drop_constraint("fk_event_route_id", type_="foreignkey")
        batch_op.drop_column("route_id")

    with op.batch_alter_table("event", schema=None) as batch_op:
        batch_op.drop_constraint("fk_event_activity_id", type_="foreignkey")
        batch_op.drop_column("activity_id")
