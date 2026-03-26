from __future__ import annotations

from flask import Flask


def create_app(*, testing: bool = False) -> Flask:
    app = Flask(__name__)
    app.config.update(
        TESTING=testing,
    )

    from app.routes import bp

    app.register_blueprint(bp)
    return app
