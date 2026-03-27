"""Seed canonical group roles

Revision ID: 30a8db42e7d8
Revises: ea981af5d0c8
Create Date: 2026-03-26 21:10:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "30a8db42e7d8"
down_revision = "ea981af5d0c8"
branch_labels = None
depends_on = None


group_role = sa.table(
    "group_role",
    sa.column("name", sa.String()),
)

ROLE_NAMES = ("admin", "member", "pending")


def upgrade() -> None:
    bind = op.get_bind()
    existing_names = {
        row[0] for row in bind.execute(sa.text("SELECT name FROM group_role")).fetchall()
    }
    missing_names = [name for name in ROLE_NAMES if name not in existing_names]
    if missing_names:
        op.bulk_insert(
            group_role,
            [{"name": name} for name in missing_names],
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM group_role WHERE name IN ('admin', 'member', 'pending')"))
