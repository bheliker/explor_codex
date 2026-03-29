"""add search documents table

Revision ID: 1cc7da553e57
Revises: 49e3252
Create Date: 2026-03-28 10:40:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1cc7da553e57"
down_revision = "7d4a2a1c9d55"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_document",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=True),
        sa.Column("subtitle", sa.String(length=256), nullable=True),
        sa.Column("location", sa.String(length=256), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_type", "entity_id", name="uq_search_document_entity"),
    )
    op.create_index(
        op.f("ix_search_document_entity_id"), "search_document", ["entity_id"], unique=False
    )
    op.create_index(
        op.f("ix_search_document_entity_type"),
        "search_document",
        ["entity_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_search_document_entity_type"), table_name="search_document")
    op.drop_index(op.f("ix_search_document_entity_id"), table_name="search_document")
    op.drop_table("search_document")
