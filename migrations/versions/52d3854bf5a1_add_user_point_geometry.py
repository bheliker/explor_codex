"""add user point geometry

Revision ID: 52d3854bf5a1
Revises: 3b12c8ef9dd0
Create Date: 2026-03-27 16:15:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "52d3854bf5a1"
down_revision = "3b12c8ef9dd0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("home_town", sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column("home_state", sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column("home_country", sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column("home_gym", sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column("home_latlng", sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column("geoll", sa.Text(), nullable=True))

    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        ALTER TABLE "user"
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
            ALTER TABLE "user"
            ALTER COLUMN geoll
            TYPE text
            USING ST_AsGeoJSON(geoll)
            """
        )

    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("geoll")
        batch_op.drop_column("home_latlng")
        batch_op.drop_column("home_gym")
        batch_op.drop_column("home_country")
        batch_op.drop_column("home_state")
        batch_op.drop_column("home_town")
