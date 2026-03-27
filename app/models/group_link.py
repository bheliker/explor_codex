from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Base


class GroupExternalUrl(Base):
    __tablename__ = "group_external_url"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str | None] = mapped_column(String(2048))
    group_id: Mapped[int | None] = mapped_column("owner", ForeignKey("group.id"))
    route_id: Mapped[int | None] = mapped_column(ForeignKey("route.id"))
    date_created: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    date_updated: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    type: Mapped[str | None] = mapped_column(String(128))
    subtype: Mapped[str | None] = mapped_column(String(128))
    name: Mapped[str | None] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(String(2048))
    tags: Mapped[str | None] = mapped_column(String(2048))
    icon: Mapped[str | None] = mapped_column(String(256))
    img: Mapped[str | None] = mapped_column(String(2048))

    group = relationship("Group", back_populates="links")
    route = relationship("Route", back_populates="links")
