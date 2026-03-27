"""add route links to group external urls

Revision ID: 2f9c7733d6df
Revises: 0fb577fba923
Create Date: 2026-03-27 13:05:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2f9c7733d6df"
down_revision = "0fb577fba923"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("group_external_url", schema=None) as batch_op:
        batch_op.add_column(sa.Column("route_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_group_external_url_route_id", "route", ["route_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("group_external_url", schema=None) as batch_op:
        batch_op.drop_constraint("fk_group_external_url_route_id", type_="foreignkey")
        batch_op.drop_column("route_id")
