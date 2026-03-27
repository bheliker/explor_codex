from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Base

if TYPE_CHECKING:
    from app.models.membership import Membership
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

    calendars = relationship("Calendar", back_populates="group")
    members = relationship("Membership", secondary=group_membership, backref="groups")

    def join(self, user: "User") -> None:
        role_name = "pending" if self.invite_only else "member"
        self.ensure_membership(user, role_name=role_name)

    def leave(self, user: "User") -> None:
        membership = self.get_membership(user)
        if membership is not None:
            self.members.remove(membership)

    def is_member(self, user: "User") -> bool:
        return self.get_membership(user) is not None

    def get_membership(self, user: "User") -> "Membership | None":
        return next((member for member in self.members if member.user_id == user.id), None)

    def ensure_membership(self, user: "User", *, role_name: str) -> "Membership":
        from app.models.lookup import GroupRole
        from app.models.membership import Membership

        role = GroupRole.by_name(role_name)
        if role is None:
            raise ValueError(f"Unknown group role: {role_name}")

        membership = self.get_membership(user)
        if membership is None:
            membership = Membership(user=user, role=role)
            self.members.append(membership)
        else:
            membership.set_role_by_name(role_name)
        return membership

    def has_role(self, user: "User", role_name: str) -> bool:
        membership = self.get_membership(user)
        return membership.has_role(role_name) if membership is not None else False

    def is_pending(self, user: "User") -> bool:
        return self.has_role(user, "pending")

    def is_admin(self, user: "User") -> bool:
        return self.has_role(user, "admin")

    def is_active_member(self, user: "User") -> bool:
        return self.has_role(user, "member") or self.has_role(user, "admin")

    def approve_membership(self, user: "User") -> "Membership":
        return self.ensure_membership(user, role_name="member")

    def promote_to_admin(self, user: "User") -> "Membership":
        return self.ensure_membership(user, role_name="admin")
