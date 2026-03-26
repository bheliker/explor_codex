from __future__ import annotations

from flask import Flask

from app.auth import init_auth
from app.config import Config, TestConfig
from app.extensions import init_extensions


def create_app(*, testing: bool = False) -> Flask:
    app = Flask(__name__)
    app.config.from_object(TestConfig if testing else Config)

    from app.routes import bp

    init_extensions(app)
    init_auth(app)

    # Ensure model modules are imported before migration commands inspect metadata.
    from app import models  # noqa: F401

    app.register_blueprint(bp)
    return app
