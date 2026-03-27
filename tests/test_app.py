from flask import Flask
from flask.testing import FlaskClient

from app.config import Config, TestConfig
from app.extensions import login_manager
from app.models import (
    Calendar,
    Event,
    EventInvitation,
    EventInvitationStatus,
    Group,
    GroupRole,
    Membership,
    User,
)


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


def test_group_membership_helpers(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]

        user = User(username="groupuser", email="groupuser@example.com", password_hash="x")
        member_role = GroupRole(id=2, name="member")
        pending_role = GroupRole(id=3, name="pending")
        group = Group(name="Explor Riders", shortname="explor-riders", invite_only=False)

        db.session.add_all([user, member_role, pending_role, group])
        db.session.commit()

        membership = Membership(user_id=user.id, role_id=member_role.id)
        group.members.append(membership)
        db.session.add(membership)
        db.session.commit()

        assert group.is_member(user) is True

        group.leave(user)
        db.session.commit()

        assert group.is_member(user) is False


def test_group_can_own_calendars(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]

        group = Group(name="Calendar Club", shortname="calendar-club")
        calendar = Calendar(name="Club Calendar", group=group, type="club")

        db.session.add_all([group, calendar])
        db.session.commit()

        assert calendar.group is not None
        assert calendar.group.name == "Calendar Club"
        assert group.calendars[0].name == "Club Calendar"


def test_calendar_can_link_events(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]

        calendar = Calendar(name="Race Calendar")
        event = Event(name="Hill Climb", town="Berkeley", state="CA", private=False)
        calendar.events.append(event)

        db.session.add(calendar)
        db.session.commit()

        assert calendar.events[0].name == "Hill Climb"
        assert event.calendars[0].name == "Race Calendar"


def test_event_can_link_participants(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]

        user = User(username="attendee", email="attendee@example.com", password_hash="x")
        status = EventInvitationStatus(name="attending")
        invitation = EventInvitation(user=user, status=status)
        event = Event(name="Spring Classic")

        event.participants.append(invitation)
        db.session.add_all([user, status, invitation, event])
        db.session.commit()

        assert event.has_participant(user) is True
        participation = event.get_participation(user)
        assert participation is not None
        assert participation.status.name == "attending"
