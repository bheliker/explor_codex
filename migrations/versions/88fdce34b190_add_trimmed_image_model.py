"""add trimmed image model

Revision ID: 88fdce34b190
Revises: 52d3854bf5a1
Create Date: 2026-03-27 16:35:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "88fdce34b190"
down_revision = "52d3854bf5a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("img_small", sa.String(length=2048), nullable=True),
        sa.Column("img_medium", sa.String(length=2048), nullable=True),
        sa.Column("img_large", sa.String(length=2048), nullable=True),
        sa.Column("img_thumb", sa.String(length=2048), nullable=True),
        sa.Column("alt_txt", sa.String(length=256), nullable=True),
        sa.Column("title", sa.String(length=256), nullable=True),
        sa.Column("caption", sa.String(length=256), nullable=True),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("segment_id", sa.Integer(), nullable=True),
        sa.Column("activity_id", sa.Integer(), nullable=True),
        sa.Column("photographer_id", sa.Integer(), nullable=True),
        sa.Column("latlng", sa.String(length=256), nullable=True),
        sa.Column("geoll", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.ForeignKeyConstraint(["activity_id"], ["activity.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["group.id"]),
        sa.ForeignKeyConstraint(["photographer_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["segment_id"], ["segment.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        ALTER TABLE image
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
            ALTER TABLE image
            ALTER COLUMN geoll
            TYPE text
            USING ST_AsGeoJSON(geoll)
            """
        )

    op.drop_table("image")
