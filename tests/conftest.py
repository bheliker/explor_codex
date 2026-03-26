from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.extensions import db


@pytest.fixture()
def app() -> Flask:
    return create_app(testing=True)


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture()
def database(app: Flask) -> Iterator[None]:
    with app.app_context():
        db.create_all()
        try:
            yield
        finally:
            db.session.remove()
            db.drop_all()
