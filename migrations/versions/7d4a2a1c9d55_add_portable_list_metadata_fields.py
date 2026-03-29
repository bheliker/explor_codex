"""add portable list metadata fields

Revision ID: 7d4a2a1c9d55
Revises: 43370fbf4c8d
Create Date: 2026-03-28 09:30:00.000000

"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7d4a2a1c9d55"
down_revision = "43370fbf4c8d"
branch_labels = None
depends_on = None


def _parse_legacy_tags(value: str | None) -> list[str] | None:
    if value is None:
        return None

    stripped = value.strip()
    if not stripped:
        return None

    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list) and all(isinstance(item, str) for item in parsed):
            return parsed

    parts = [part.strip() for part in stripped.split(",")]
    return [part for part in parts if part] or None


def upgrade() -> None:
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("preference_tags", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("tags", sa.JSON(), nullable=True))

    with op.batch_alter_table("group", schema=None) as batch_op:
        batch_op.add_column(sa.Column("preference_tags", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("tags", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("rider_classes", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("ride_classes", sa.JSON(), nullable=True))

    with op.batch_alter_table("activity", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tags", sa.JSON(), nullable=True))

    with op.batch_alter_table("calendar", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tags", sa.JSON(), nullable=True))

    with op.batch_alter_table("event", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tags", sa.JSON(), nullable=True))

    with op.batch_alter_table("image", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tags", sa.JSON(), nullable=True))

    with op.batch_alter_table("points_of_interest", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tags", sa.JSON(), nullable=True))

    with op.batch_alter_table("group_dues", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tags", sa.JSON(), nullable=True))

    with op.batch_alter_table("event_fee", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tags", sa.JSON(), nullable=True))

    with op.batch_alter_table("group_external_url", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tags_json", sa.JSON(), nullable=True))

    bind = op.get_bind()
    select_links = sa.text("SELECT id, tags FROM group_external_url WHERE tags IS NOT NULL")
    rows = bind.execute(select_links).fetchall()
    for row in rows:
        parsed = _parse_legacy_tags(row.tags)
        if parsed is None:
            continue
        bind.execute(
            sa.text("UPDATE group_external_url SET tags_json = :tags WHERE id = :id"),
            {"id": row.id, "tags": json.dumps(parsed)},
        )

    with op.batch_alter_table("group_external_url", schema=None) as batch_op:
        batch_op.drop_column("tags")
        batch_op.alter_column("tags_json", new_column_name="tags")


def downgrade() -> None:
    with op.batch_alter_table("group_external_url", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tags_legacy", sa.String(length=2048), nullable=True))

    bind = op.get_bind()
    select_links = sa.text("SELECT id, tags FROM group_external_url WHERE tags IS NOT NULL")
    rows = bind.execute(select_links).fetchall()
    for row in rows:
        if isinstance(row.tags, str):
            rendered = row.tags
        else:
            try:
                rendered = ",".join(row.tags)
            except TypeError:
                rendered = None
        if rendered is None:
            continue
        bind.execute(
            sa.text("UPDATE group_external_url SET tags_legacy = :tags WHERE id = :id"),
            {"id": row.id, "tags": rendered},
        )

    with op.batch_alter_table("group_external_url", schema=None) as batch_op:
        batch_op.drop_column("tags")
        batch_op.alter_column("tags_legacy", new_column_name="tags")

    with op.batch_alter_table("event_fee", schema=None) as batch_op:
        batch_op.drop_column("tags")

    with op.batch_alter_table("group_dues", schema=None) as batch_op:
        batch_op.drop_column("tags")

    with op.batch_alter_table("points_of_interest", schema=None) as batch_op:
        batch_op.drop_column("tags")

    with op.batch_alter_table("image", schema=None) as batch_op:
        batch_op.drop_column("tags")

    with op.batch_alter_table("event", schema=None) as batch_op:
        batch_op.drop_column("tags")

    with op.batch_alter_table("calendar", schema=None) as batch_op:
        batch_op.drop_column("tags")

    with op.batch_alter_table("activity", schema=None) as batch_op:
        batch_op.drop_column("tags")

    with op.batch_alter_table("group", schema=None) as batch_op:
        batch_op.drop_column("ride_classes")
        batch_op.drop_column("rider_classes")
        batch_op.drop_column("tags")
        batch_op.drop_column("preference_tags")

    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("tags")
        batch_op.drop_column("preference_tags")
