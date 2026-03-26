from __future__ import annotations

from datetime import UTC, datetime

from flask import current_app
from flask_login import UserMixin  # type: ignore[import-untyped]
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import Base, db


class User(UserMixin, Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(db.String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(db.String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(db.String(255))
    firstname: Mapped[str | None] = mapped_column(db.String(64))
    lastname: Mapped[str | None] = mapped_column(db.String(64))
    account_type: Mapped[str | None] = mapped_column(db.String(64))
    active: Mapped[bool] = mapped_column(default=True)
    init_date: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    update_date: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    last_login_at: Mapped[datetime | None]

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_reset_password_token(self) -> str:
        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        return serializer.dumps({"reset_password": self.id}, salt="reset-password")

    @staticmethod
    def verify_reset_password_token(token: str, *, max_age: int = 600) -> "User | None":
        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        try:
            payload = serializer.loads(token, salt="reset-password", max_age=max_age)
        except (BadSignature, SignatureExpired):
            return None
        return db.session.get(User, payload["reset_password"])
