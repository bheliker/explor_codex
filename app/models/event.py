from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Base
from app.geometry import point_type, to_api_point_geometry, to_storage_point_geometry

if TYPE_CHECKING:
    from app.models.membership import EventInvitation
    from app.models.user import User

calendar_events = Table(
    "calendar_events",
    Base.metadata,
    Column("calendars", Integer, ForeignKey("calendar.id"), primary_key=True),
    Column("events", Integer, ForeignKey("event.id"), primary_key=True),
)

event_images = Table(
    "event_images",
    Base.metadata,
    Column("event", Integer, ForeignKey("event.id"), primary_key=True),
    Column("image", Integer, ForeignKey("image.id"), primary_key=True),
)


class Event(Base):
    __tablename__ = "event"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(String(2048))
    private: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    email: Mapped[str | None] = mapped_column(String(120))
    date_start: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    date_end: Mapped[datetime | None]
    date_created: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    date_updated: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    duration: Mapped[float | None] = mapped_column(Float)
    primary_activity: Mapped[str | None] = mapped_column(String(64))
    type: Mapped[str | None] = mapped_column(String(256))
    subtype: Mapped[str | None] = mapped_column(String(256))
    url: Mapped[str | None] = mapped_column(String(2048))
    reg_url: Mapped[str | None] = mapped_column(String(2048))
    photo_url: Mapped[str | None] = mapped_column(String(2048))
    logo: Mapped[str | None] = mapped_column(String(2048))
    profile_photo: Mapped[str | None] = mapped_column(String(2048))
    notes: Mapped[str | None] = mapped_column(String(2048))
    lon: Mapped[float | None] = mapped_column(Float)
    lat: Mapped[float | None] = mapped_column(Float)
    town: Mapped[str | None] = mapped_column(String(256))
    state: Mapped[str | None] = mapped_column(String(256))
    country: Mapped[str | None] = mapped_column(String(256))
    latlng: Mapped[str | None] = mapped_column(String(256))
    _geoll: Mapped[object | None] = mapped_column("geoll", point_type())
    route_id: Mapped[int | None] = mapped_column(ForeignKey("route.id"))
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("activity.id"))

    calendars = relationship("Calendar", secondary=calendar_events, back_populates="events")
    fees = relationship("EventFee", back_populates="event")
    route = relationship("Route")
    activity = relationship("Activity")
    images = relationship("Image", secondary=event_images, back_populates="events")
    participants = relationship(
        "EventInvitation",
        secondary="event_attendance",
        back_populates="events",
    )

    def get_participation(self, user: User) -> EventInvitation | None:
        return next(
            (participant for participant in self.participants if participant.user_id == user.id),
            None,
        )

    def has_participant(self, user: User) -> bool:
        return self.get_participation(user) is not None

    def ensure_participation(self, user: User, *, status_name: str) -> EventInvitation:
        from app.models.lookup import EventInvitationStatus
        from app.models.membership import EventInvitation

        status = EventInvitationStatus.by_name(status_name)
        if status is None:
            raise ValueError(f"Unknown event invitation status: {status_name}")

        participation = self.get_participation(user)
        if participation is None:
            participation = EventInvitation(user=user, status=status)
            self.participants.append(participation)
        else:
            participation.status = status
        return participation

    def invite(self, user: User) -> EventInvitation:
        return self.ensure_participation(user, status_name="invited")

    def mark_interested(self, user: User) -> EventInvitation:
        return self.ensure_participation(user, status_name="interested")

    def mark_attending(self, user: User) -> EventInvitation:
        return self.ensure_participation(user, status_name="attending")

    def mark_not_attending(self, user: User) -> EventInvitation:
        return self.ensure_participation(user, status_name="not_attending")

    @property
    def geoll(self) -> str | None:
        return to_api_point_geometry(self, "geoll", self._geoll)

    @geoll.setter
    def geoll(self, value: str | None) -> None:
        self._geoll = to_storage_point_geometry(value)
