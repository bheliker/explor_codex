from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Base
from app.models.event import calendar_events


class Calendar(Base):
    __tablename__ = "calendar"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(String(2048))
    private: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[int | None] = mapped_column("owner", Integer)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("group.id"))
    tags: Mapped[list[str] | None] = mapped_column(JSON)
    date_created: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    date_updated: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    primary_activity: Mapped[str | None] = mapped_column(String(64))
    type: Mapped[str | None] = mapped_column(String(256))
    subtype: Mapped[str | None] = mapped_column(String(256))
    url: Mapped[str | None] = mapped_column(String(2048))
    photo_url: Mapped[str | None] = mapped_column(String(2048))
    logo: Mapped[str | None] = mapped_column(String(2048))
    profile_photo: Mapped[str | None] = mapped_column(String(2048))
    notes: Mapped[str | None] = mapped_column(String(2048))

    events = relationship("Event", secondary=calendar_events, back_populates="calendars")
    group = relationship("Group", back_populates="calendars")
