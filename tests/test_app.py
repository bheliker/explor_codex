from flask import Flask
from flask.testing import FlaskClient

from app.config import Config, TestConfig
from app.extensions import login_manager
from app.models import EventInvitation, EventInvitationStatus, GroupRole, Membership, User


def test_index_route(client: FlaskClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.get_json() == {"message": "explor_codex is ready"}


def test_health_route(client: FlaskClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_app_factory_enables_testing_config(app: Flask) -> None:
    assert app.testing is True


def test_app_registers_sqlalchemy_extension(app: Flask) -> None:
    assert "sqlalchemy" in app.extensions


def test_test_config_uses_in_memory_sqlite() -> None:
    assert TestConfig.SQLALCHEMY_DATABASE_URI == "sqlite+pysqlite:///:memory:"


def test_config_normalizes_legacy_postgres_url() -> None:
    assert Config.SQLALCHEMY_DATABASE_URI.startswith("postgresql+psycopg://")


def test_app_registers_login_manager() -> None:
    assert login_manager.login_view == "auth.login"


def test_user_password_and_reset_token_round_trip(app: Flask, database: None) -> None:
    with app.app_context():
        user = User(username="brett", email="brett@example.com")
        user.set_password("secret123")
        db = app.extensions["sqlalchemy"]
        db.session.add(user)
        db.session.commit()

        assert user.check_password("secret123") is True
        token = user.get_reset_password_token()

        restored = User.verify_reset_password_token(token)
        assert restored is not None
        assert restored.id == user.id


def test_membership_models_persist_relationships(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]

        user = User(username="member", email="member@example.com", password_hash="x")
        role = GroupRole(name="organizer")
        status = EventInvitationStatus(name="attending")
        db.session.add_all([user, role, status])
        db.session.commit()

        membership = Membership(user_id=user.id, role_id=role.id)
        invitation = EventInvitation(user_id=user.id, status_id=status.id)
        db.session.add_all([membership, invitation])
        db.session.commit()

        assert membership.user.id == user.id
        assert membership.role.name == "organizer"
        assert invitation.status.name == "attending"
