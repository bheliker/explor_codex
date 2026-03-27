from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Base

route_segments = Table(
    "route_segments",
    Base.metadata,
    Column("routes", ForeignKey("route.id"), primary_key=True),
    Column("segments", ForeignKey("segment.id"), primary_key=True),
)


class Segment(Base):
    __tablename__ = "segment"

    id: Mapped[int] = mapped_column(primary_key=True)
    init_date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    update_date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    name: Mapped[str | None] = mapped_column(String(2048))
    desc: Mapped[str | None] = mapped_column(String(2048))
    duration: Mapped[float | None] = mapped_column(Float)
    length: Mapped[float | None] = mapped_column(Float)
    elevation_gain: Mapped[float | None] = mapped_column(Float)
    elevation_loss: Mapped[float | None] = mapped_column(Float)
    elev_high: Mapped[float | None] = mapped_column(Float)
    elev_low: Mapped[float | None] = mapped_column(Float)
    rating: Mapped[float | None] = mapped_column(Float)
    grade: Mapped[float | None] = mapped_column(Float)
    type: Mapped[str | None] = mapped_column(String(128))
    subtype: Mapped[str | None] = mapped_column(String(128))
    src: Mapped[str | None] = mapped_column(String(128))
    src_id: Mapped[str | None] = mapped_column(String(128))
    src_url: Mapped[str | None] = mapped_column(String(2048))
    start_longitude: Mapped[float | None] = mapped_column(Float)
    start_latitude: Mapped[float | None] = mapped_column(Float)
    end_longitude: Mapped[float | None] = mapped_column(Float)
    end_latitude: Mapped[float | None] = mapped_column(Float)
    track_hash: Mapped[str | None] = mapped_column(String(32), index=True, unique=True)
    track_maxspeed: Mapped[float | None] = mapped_column(Float)
    record_date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    routes = relationship("Route", secondary=route_segments, back_populates="segments")
