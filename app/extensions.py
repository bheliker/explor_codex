from __future__ import annotations

from flask import Flask
from flask_login import LoginManager  # type: ignore[import-untyped]
from flask_migrate import Migrate  # type: ignore[import-untyped]
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
migrate = Migrate(compare_type=True)


def init_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    app.extensions["email_outbox"] = []

    from app.services.search import register_search_listeners

    register_search_listeners()
