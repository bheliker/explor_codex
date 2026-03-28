"""add group point geometry

Revision ID: 3b12c8ef9dd0
Revises: c3c9ae17d746
Create Date: 2026-03-27 15:55:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3b12c8ef9dd0"
down_revision = "c3c9ae17d746"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("group", schema=None) as batch_op:
        batch_op.add_column(sa.Column("geoll", sa.Text(), nullable=True))

    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        ALTER TABLE "group"
        ALTER COLUMN geoll
        TYPE geometry(POINT)
        USING CASE
            WHEN geoll IS NULL THEN NULL
            WHEN left(trim(geoll), 1) = '{' THEN ST_GeomFromGeoJSON(geoll)
            ELSE ST_GeomFromText(geoll)
        END
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            ALTER TABLE "group"
            ALTER COLUMN geoll
            TYPE text
            USING ST_AsGeoJSON(geoll)
            """
        )

    with op.batch_alter_table("group", schema=None) as batch_op:
        batch_op.drop_column("geoll")
