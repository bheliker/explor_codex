"""Seed event invitation statuses

Revision ID: ea981af5d0c8
Revises: bfa1b258d025
Create Date: 2026-03-26 20:50:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "ea981af5d0c8"
down_revision = "bfa1b258d025"
branch_labels = None
depends_on = None


event_invitation_status = sa.table(
    "event_invitation_status",
    sa.column("name", sa.String()),
)

STATUS_NAMES = ("invited", "attending", "interested", "not_attending")


def upgrade() -> None:
    bind = op.get_bind()
    existing_names = {
        row[0]
        for row in bind.execute(sa.text("SELECT name FROM event_invitation_status")).fetchall()
    }
    missing_names = [name for name in STATUS_NAMES if name not in existing_names]
    if missing_names:
        op.bulk_insert(
            event_invitation_status,
            [{"name": name} for name in missing_names],
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM event_invitation_status "
            "WHERE name IN ('invited', 'attending', 'interested', 'not_attending')"
        )
    )
