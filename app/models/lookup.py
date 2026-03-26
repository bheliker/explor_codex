from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import Base


class GroupRole(Base):
    __tablename__ = "group_role"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)


class EventInvitationStatus(Base):
    __tablename__ = "event_invitation_status"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
