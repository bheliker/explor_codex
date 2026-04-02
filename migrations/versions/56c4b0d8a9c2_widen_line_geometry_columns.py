"""widen line geometry columns

Revision ID: 56c4b0d8a9c2
Revises: 0d7f4ee1d1fa
Create Date: 2026-04-01 16:30:00.000000

"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "56c4b0d8a9c2"
down_revision = "0d7f4ee1d1fa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    for table_name in ("route", "segment", "activity"):
        op.execute(
            f"""
            ALTER TABLE {table_name}
            ALTER COLUMN summary_polyline
            TYPE geometry(GEOMETRY)
            USING summary_polyline
            """
        )
        op.execute(
            f"""
            ALTER TABLE {table_name}
            ALTER COLUMN full_track
            TYPE geometry(GEOMETRYZ)
            USING full_track
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    for table_name in ("activity", "segment", "route"):
        op.execute(
            f"""
            ALTER TABLE {table_name}
            ALTER COLUMN full_track
            TYPE geometry(LINESTRINGZ)
            USING CASE
                WHEN full_track IS NULL THEN NULL
                WHEN GeometryType(full_track) = 'MULTILINESTRING'
                    THEN ST_GeometryN(full_track, 1)
                ELSE full_track
            END
            """
        )
        op.execute(
            f"""
            ALTER TABLE {table_name}
            ALTER COLUMN summary_polyline
            TYPE geometry(LINESTRING)
            USING CASE
                WHEN summary_polyline IS NULL THEN NULL
                WHEN GeometryType(summary_polyline) = 'MULTILINESTRING'
                    THEN ST_GeometryN(summary_polyline, 1)
                ELSE summary_polyline
            END
            """
        )
