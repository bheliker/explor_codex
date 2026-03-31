from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.extensions import db
from app.models import User


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


@pytest.fixture()
def admin_user_id(app: Flask, database: None) -> int:
    with app.app_context():
        user = User(
            username="site-admin",
            email="admin@example.com",
            active=True,
            site_admin=True,
        )
        user.set_password("secret123")
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture()
def admin_client(client: FlaskClient, admin_user_id: int) -> FlaskClient:
    with client.session_transaction() as session:
        session["_user_id"] = str(admin_user_id)
        session["_fresh"] = True
    return client
