from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Base

if TYPE_CHECKING:
    from app.models.user import User


group_membership = Table(
    "group_membership",
    Base.metadata,
    Column("groups", Integer, ForeignKey("group.id"), primary_key=True),
    Column("members", Integer, ForeignKey("membership.id"), primary_key=True),
)


class Group(Base):
    __tablename__ = "group"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    shortname: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    abbreviation: Mapped[str | None] = mapped_column(String(64))
    contact: Mapped[str | None] = mapped_column(String(120))
    contact_sec: Mapped[str | None] = mapped_column(String(120))
    about_blurb: Mapped[str | None] = mapped_column(String(2400))
    more_info_url: Mapped[str | None] = mapped_column(String(2400))
    private: Mapped[bool] = mapped_column(Boolean, default=False)
    invite_only: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    verified: Mapped[int | None] = mapped_column(Integer)
    init_date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    update_date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    membership_level: Mapped[int | None] = mapped_column(Integer)
    account_type: Mapped[str | None] = mapped_column(String(64))
    group_type: Mapped[str | None] = mapped_column(String(64))
    category: Mapped[str | None] = mapped_column(String(128))
    primary_activity: Mapped[str | None] = mapped_column(String(64))
    type: Mapped[str | None] = mapped_column(String(128))
    subtype: Mapped[str | None] = mapped_column(String(128))
    date_founded: Mapped[datetime | None]
    dues: Mapped[float | None] = mapped_column(Float)
    waiver_url: Mapped[str | None] = mapped_column(String(2048))
    waiver_date: Mapped[datetime | None]
    logo: Mapped[str | None] = mapped_column(String(2048))
    profile_photo: Mapped[str | None] = mapped_column(String(2048))
    hero_video: Mapped[str | None] = mapped_column(String(2048))
    home_town: Mapped[str | None] = mapped_column(String(256))
    home_state: Mapped[str | None] = mapped_column(String(256))
    home_country: Mapped[str | None] = mapped_column(String(256))
    home_latlng: Mapped[str | None] = mapped_column(String(256))
    home_add: Mapped[str | None] = mapped_column(String(256))
    full_address: Mapped[str | None] = mapped_column(String(2048))
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))

    members = relationship("Membership", secondary=group_membership, backref="groups")

    def join(self, user: "User") -> None:
        if not self.is_member(user):
            role_id = 3 if self.invite_only else 2
            from app.models.membership import Membership

            self.members.append(Membership(user_id=user.id, role_id=role_id))

    def leave(self, user: "User") -> None:
        membership = next((member for member in self.members if member.user_id == user.id), None)
        if membership is not None:
            self.members.remove(membership)

    def is_member(self, user: "User") -> bool:
        return any(member.user_id == user.id for member in self.members)
