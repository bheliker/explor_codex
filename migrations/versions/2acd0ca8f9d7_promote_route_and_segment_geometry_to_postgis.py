"""promote route and segment geometry to postgis

Revision ID: 2acd0ca8f9d7
Revises: 20c2164420a2
Create Date: 2026-03-27 14:20:00.000000

"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "2acd0ca8f9d7"
down_revision = "20c2164420a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        ALTER TABLE route
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
        ALTER TABLE route
        ALTER COLUMN full_track
        TYPE geometry(LINESTRINGZ)
        USING CASE
            WHEN full_track IS NULL THEN NULL
            WHEN left(trim(full_track), 1) = '{' THEN ST_GeomFromGeoJSON(full_track)
            ELSE ST_GeomFromText(full_track)
        END
        """
    )
    op.execute(
        """
        ALTER TABLE segment
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
        ALTER TABLE segment
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
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        ALTER TABLE segment
        ALTER COLUMN full_track
        TYPE text
        USING ST_AsGeoJSON(full_track)
        """
    )
    op.execute(
        """
        ALTER TABLE segment
        ALTER COLUMN summary_polyline
        TYPE text
        USING ST_AsGeoJSON(summary_polyline)
        """
    )
    op.execute(
        """
        ALTER TABLE route
        ALTER COLUMN full_track
        TYPE text
        USING ST_AsGeoJSON(full_track)
        """
    )
    op.execute(
        """
        ALTER TABLE route
        ALTER COLUMN summary_polyline
        TYPE text
        USING ST_AsGeoJSON(summary_polyline)
        """
    )
