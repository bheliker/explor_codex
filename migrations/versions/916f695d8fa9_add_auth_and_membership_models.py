"""Add auth and membership models

Revision ID: 916f695d8fa9
Revises: 64c523e57c65
Create Date: 2026-03-26 15:27:02.254694

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "916f695d8fa9"
down_revision = "64c523e57c65"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("firstname", sa.String(length=64), nullable=True),
        sa.Column("lastname", sa.String(length=64), nullable=True),
        sa.Column("account_type", sa.String(length=64), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("init_date", sa.DateTime(), nullable=False),
        sa.Column("update_date", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_user_email"), ["email"], unique=True)
        batch_op.create_index(batch_op.f("ix_user_username"), ["username"], unique=True)

    op.create_table(
        "event_invitation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status_id", sa.Integer(), nullable=False),
        sa.Column("rsvp_date", sa.DateTime(), nullable=False),
        sa.Column("fee_paid_date", sa.DateTime(), nullable=True),
        sa.Column("waiver_date", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["status_id"], ["event_invitation_status.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("event_invitation", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_event_invitation_status_id"),
            ["status_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_event_invitation_user_id"),
            ["user_id"],
            unique=False,
        )

    op.create_table(
        "membership",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("join_date", sa.DateTime(), nullable=False),
        sa.Column("dues_paid_date", sa.DateTime(), nullable=True),
        sa.Column("waiver_date", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["role_id"], ["group_role.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("membership", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_membership_role_id"), ["role_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_membership_user_id"), ["user_id"], unique=False)

    with op.batch_alter_table("event_invitation_status", schema=None) as batch_op:
        batch_op.add_column(sa.Column("name", sa.String(), nullable=True))

    op.execute("UPDATE event_invitation_status SET name = status")

    with op.batch_alter_table("event_invitation_status", schema=None) as batch_op:
        batch_op.alter_column("name", nullable=False)
        batch_op.create_unique_constraint("uq_event_invitation_status_name", ["name"])
        batch_op.drop_column("status")


def downgrade() -> None:
    with op.batch_alter_table("event_invitation_status", schema=None) as batch_op:
        batch_op.add_column(sa.Column("status", sa.VARCHAR(), nullable=True))

    op.execute("UPDATE event_invitation_status SET status = name")

    with op.batch_alter_table("event_invitation_status", schema=None) as batch_op:
        batch_op.alter_column("status", nullable=False)
        batch_op.drop_constraint("uq_event_invitation_status_name", type_="unique")
        batch_op.drop_column("name")

    with op.batch_alter_table("membership", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_membership_user_id"))
        batch_op.drop_index(batch_op.f("ix_membership_role_id"))

    op.drop_table("membership")
    with op.batch_alter_table("event_invitation", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_event_invitation_user_id"))
        batch_op.drop_index(batch_op.f("ix_event_invitation_status_id"))

    op.drop_table("event_invitation")
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_user_username"))
        batch_op.drop_index(batch_op.f("ix_user_email"))

    op.drop_table("user")
