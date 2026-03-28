"""add event point geometry

Revision ID: 54ef7b0af8c1
Revises: bc20f8ca4d31
Create Date: 2026-03-27 17:35:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "54ef7b0af8c1"
down_revision = "bc20f8ca4d31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("event", schema=None) as batch_op:
        batch_op.add_column(sa.Column("geoll", sa.Text(), nullable=True))

    op.execute(
        """
        UPDATE event
        SET geoll = '{"type":"Point","coordinates":[' || lon || ',' || lat || ']}'
        WHERE geoll IS NULL AND lon IS NOT NULL AND lat IS NOT NULL
        """
    )

    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        ALTER TABLE event
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
            ALTER TABLE event
            ALTER COLUMN geoll
            TYPE text
            USING ST_AsGeoJSON(geoll)
            """
        )

    with op.batch_alter_table("event", schema=None) as batch_op:
        batch_op.drop_column("geoll")
