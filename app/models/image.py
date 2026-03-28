from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Base
from app.geometry import point_type, to_api_point_geometry, to_storage_point_geometry


class Image(Base):
    __tablename__ = "image"

    id: Mapped[int] = mapped_column(primary_key=True)
    img_small: Mapped[str | None] = mapped_column(String(2048))
    img_medium: Mapped[str | None] = mapped_column(String(2048))
    img_large: Mapped[str | None] = mapped_column(String(2048))
    img_thumb: Mapped[str | None] = mapped_column(String(2048))
    alt_txt: Mapped[str | None] = mapped_column(String(256))
    title: Mapped[str | None] = mapped_column(String(256))
    caption: Mapped[str | None] = mapped_column(String(256))
    date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("group.id"))
    segment_id: Mapped[int | None] = mapped_column(ForeignKey("segment.id"))
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("activity.id"))
    photographer_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    latlng: Mapped[str | None] = mapped_column(String(256))
    _geoll: Mapped[object | None] = mapped_column("geoll", point_type())
    url: Mapped[str | None] = mapped_column(String(2048))

    group = relationship("Group", foreign_keys=[group_id])
    segment = relationship("Segment", back_populates="images")
    activity = relationship("Activity", back_populates="images")
    photographer = relationship("User")

    @property
    def geoll(self) -> str | None:
        return to_api_point_geometry(self, "geoll", self._geoll)

    @geoll.setter
    def geoll(self, value: str | None) -> None:
        self._geoll = to_storage_point_geometry(value)
