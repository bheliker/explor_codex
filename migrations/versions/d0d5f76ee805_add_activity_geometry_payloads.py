"""add activity geometry payloads

Revision ID: d0d5f76ee805
Revises: 2acd0ca8f9d7
Create Date: 2026-03-27 15:15:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d0d5f76ee805"
down_revision = "2acd0ca8f9d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("activity", schema=None) as batch_op:
        batch_op.add_column(sa.Column("summary_polyline", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("full_track", sa.Text(), nullable=True))

    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        ALTER TABLE activity
        ALTER COLUMN summary_polyline
        TYPE geometry(LINESTRING)
        USING CASE
            WHEN summary_polyline IS NULL THEN NULL
            WHEN left(trim(summary_polyline), 1) = '{' THEN ST_GeomFromGeoJSON(summary_polyline)
            ELSE ST_GeomFromText(summary_polyline)
        END
        """
    )
    op.execute(
        """
        ALTER TABLE activity
        ALTER COLUMN full_track
        TYPE geometry(LINESTRINGZ)
        USING CASE
            WHEN full_track IS NULL THEN NULL
            WHEN left(trim(full_track), 1) = '{' THEN ST_GeomFromGeoJSON(full_track)
            ELSE ST_GeomFromText(full_track)
        END
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            ALTER TABLE activity
            ALTER COLUMN full_track
            TYPE text
            USING ST_AsGeoJSON(full_track)
            """
        )
        op.execute(
            """
            ALTER TABLE activity
            ALTER COLUMN summary_polyline
            TYPE text
            USING ST_AsGeoJSON(summary_polyline)
            """
        )

    with op.batch_alter_table("activity", schema=None) as batch_op:
        batch_op.drop_column("full_track")
        batch_op.drop_column("summary_polyline")
