"""add user units preference

Revision ID: f24d3d3b9c1a
Revises: 0d7f4ee1d1fa
Create Date: 2026-04-02 10:30:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f24d3d3b9c1a"
down_revision = "0d7f4ee1d1fa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user", sa.Column("units", sa.String(length=16), nullable=True))
    op.execute("UPDATE user SET units = 'metric' WHERE units IS NULL")
    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column("units", existing_type=sa.String(length=16), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("units")
