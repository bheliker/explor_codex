"""add group hero photo link

Revision ID: bc20f8ca4d31
Revises: 88fdce34b190
Create Date: 2026-03-27 17:05:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "bc20f8ca4d31"
down_revision = "88fdce34b190"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("group", schema=None) as batch_op:
        batch_op.add_column(sa.Column("hero_photo_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_group_hero_photo_id_image",
            "image",
            ["hero_photo_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("group", schema=None) as batch_op:
        batch_op.drop_constraint("fk_group_hero_photo_id_image", type_="foreignkey")
        batch_op.drop_column("hero_photo_id")
