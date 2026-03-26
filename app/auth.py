from __future__ import annotations

from flask import Flask

from app.extensions import login_manager


def init_auth(app: Flask) -> None:
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str) -> object | None:
        from app.extensions import db
        from app.models import User

        return db.session.get(User, int(user_id))
