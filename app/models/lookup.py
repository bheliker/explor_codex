from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import Base, db

EVENT_INVITATION_STATUS_NAMES = (
    "invited",
    "attending",
    "interested",
    "not_attending",
)


class GroupRole(Base):
    __tablename__ = "group_role"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)


class EventInvitationStatus(Base):
    __tablename__ = "event_invitation_status"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)

    @classmethod
    def by_name(cls, name: str) -> "EventInvitationStatus | None":
        return db.session.query(cls).filter_by(name=name).one_or_none()


def missing_event_invitation_status_names(existing_names: Iterable[str]) -> list[str]:
    known = set(existing_names)
    return [name for name in EVENT_INVITATION_STATUS_NAMES if name not in known]
