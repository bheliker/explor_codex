from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Base
from app.geometry import point_type, to_api_point_geometry, to_storage_point_geometry


class PointOfInterest(Base):
    __tablename__ = "points_of_interest"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int | None] = mapped_column("owner", ForeignKey("user.id"))
    type: Mapped[str | None] = mapped_column(String(128))
    subtype: Mapped[str | None] = mapped_column(String(128))
    lon: Mapped[float | None] = mapped_column(Float)
    lat: Mapped[float | None] = mapped_column(Float)
    _geoll: Mapped[object | None] = mapped_column("geoll", point_type())
    name: Mapped[str | None] = mapped_column(String(256))
    url: Mapped[str | None] = mapped_column(String(2048))
    description: Mapped[str | None] = mapped_column(String(2048))
    date_created: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    date_updated: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    icon: Mapped[str | None] = mapped_column(String(256))

    owner = relationship("User")

    @property
    def geoll(self) -> str | None:
        return to_api_point_geometry(self, "geoll", self._geoll)

    @geoll.setter
    def geoll(self, value: str | None) -> None:
        self._geoll = to_storage_point_geometry(value)
