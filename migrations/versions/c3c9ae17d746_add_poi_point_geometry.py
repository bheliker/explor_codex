"""add poi point geometry

Revision ID: c3c9ae17d746
Revises: d0d5f76ee805
Create Date: 2026-03-27 15:35:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3c9ae17d746"
down_revision = "d0d5f76ee805"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("points_of_interest", schema=None) as batch_op:
        batch_op.add_column(sa.Column("geoll", sa.Text(), nullable=True))

    op.execute(
        """
        UPDATE points_of_interest
        SET geoll = '{"type":"Point","coordinates":[' || lon || ',' || lat || ']}'
        WHERE geoll IS NULL AND lon IS NOT NULL AND lat IS NOT NULL
        """
    )

    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        ALTER TABLE points_of_interest
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
            ALTER TABLE points_of_interest
            ALTER COLUMN geoll
            TYPE text
            USING ST_AsGeoJSON(geoll)
            """
        )

    with op.batch_alter_table("points_of_interest", schema=None) as batch_op:
        batch_op.drop_column("geoll")
