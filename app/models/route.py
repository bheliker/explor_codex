from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Base
from app.geometry import linestring_type, linestring_z_type, to_api_geometry, to_storage_geometry

if TYPE_CHECKING:
    pass


class Route(Base):
    __tablename__ = "route"

    id: Mapped[int] = mapped_column(primary_key=True)
    init_date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    update_date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    name: Mapped[str | None] = mapped_column(String(2048))
    desc: Mapped[str | None] = mapped_column(String(2048))
    athlete_id: Mapped[int | None]
    creator_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    private: Mapped[bool | None] = mapped_column(Boolean)
    duration: Mapped[float | None] = mapped_column(Float)
    length: Mapped[float | None] = mapped_column(Float)
    elevation_gain: Mapped[float | None] = mapped_column(Float)
    type: Mapped[str | None] = mapped_column(String(128))
    subtype: Mapped[str | None] = mapped_column(String(128))
    grade: Mapped[float | None] = mapped_column(Float)
    rating: Mapped[float | None] = mapped_column(Float)
    src: Mapped[str | None] = mapped_column(String(128))
    src_id: Mapped[str | None] = mapped_column(String(128))
    start_longitude: Mapped[float | None] = mapped_column(Float)
    start_latitude: Mapped[float | None] = mapped_column(Float)
    end_longitude: Mapped[float | None] = mapped_column(Float)
    end_latitude: Mapped[float | None] = mapped_column(Float)
    _summary_polyline: Mapped[object | None] = mapped_column("summary_polyline", linestring_type())
    _full_track: Mapped[object | None] = mapped_column("full_track", linestring_z_type())
    map_thumbnail: Mapped[str | None] = mapped_column(String(2048))
    city: Mapped[str | None] = mapped_column(String(256))
    state: Mapped[str | None] = mapped_column(String(256))
    country: Mapped[str | None] = mapped_column(String(256))
    address: Mapped[str | None] = mapped_column(String(2048))

    creator = relationship("User")
    groups = relationship("Group", secondary="group_routes", back_populates="routes")
    links = relationship("GroupExternalUrl", back_populates="route")
    segments = relationship("Segment", secondary="route_segments", back_populates="routes")

    @property
    def summary_polyline(self) -> str | None:
        return to_api_geometry(self, "summary_polyline", self._summary_polyline)

    @summary_polyline.setter
    def summary_polyline(self, value: str | None) -> None:
        self._summary_polyline = to_storage_geometry(value)

    @property
    def full_track(self) -> str | None:
        return to_api_geometry(self, "full_track", self._full_track)

    @full_track.setter
    def full_track(self, value: str | None) -> None:
        self._full_track = to_storage_geometry(value)
