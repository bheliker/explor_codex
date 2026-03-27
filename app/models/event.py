from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Base

calendar_events = Table(
    "calendar_events",
    Base.metadata,
    Column("calendars", Integer, ForeignKey("calendar.id"), primary_key=True),
    Column("events", Integer, ForeignKey("event.id"), primary_key=True),
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

    calendars = relationship("Calendar", secondary=calendar_events, back_populates="events")
