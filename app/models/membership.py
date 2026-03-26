from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Base


class Membership(Base):
    __tablename__ = "membership"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("group_role.id"), index=True)
    join_date: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    dues_paid_date: Mapped[datetime | None]
    waiver_date: Mapped[datetime | None]

    user = relationship("User")
    role = relationship("GroupRole")


class EventInvitation(Base):
    __tablename__ = "event_invitation"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    status_id: Mapped[int] = mapped_column(
        ForeignKey("event_invitation_status.id"),
        index=True,
    )
    rsvp_date: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    fee_paid_date: Mapped[datetime | None]
    waiver_date: Mapped[datetime | None]

    user = relationship("User")
    status = relationship("EventInvitationStatus")
