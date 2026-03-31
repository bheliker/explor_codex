"""add site admin flag to users

Revision ID: 9815df31c0ad
Revises: 1cc7da553e57
Create Date: 2026-03-30 17:05:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9815df31c0ad"
down_revision = "1cc7da553e57"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("site_admin", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    connection = op.get_bind()
    user_table = sa.table(
        "user",
        sa.column("id", sa.Integer()),
        sa.column("site_admin", sa.Boolean()),
    )
    active_admin_count = connection.execute(
        sa.select(sa.func.count()).select_from(user_table).where(user_table.c.site_admin.is_(True))
    ).scalar_one()

    if active_admin_count == 0:
        first_user_id = connection.execute(sa.select(sa.func.min(user_table.c.id))).scalar_one()
        if first_user_id is not None:
            connection.execute(
                user_table.update().where(user_table.c.id == first_user_id).values(site_admin=True)
            )

    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.alter_column("site_admin", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("site_admin")
