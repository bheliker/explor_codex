from flask import Flask
from flask.testing import FlaskClient

from app.config import Config, TestConfig
from app.extensions import login_manager
from app.models import (
    EVENT_INVITATION_STATUS_NAMES,
    GROUP_ROLE_NAMES,
    Calendar,
    Event,
    EventFee,
    EventInvitation,
    EventInvitationStatus,
    Group,
    GroupDues,
    GroupExternalUrl,
    GroupRole,
    Membership,
    User,
    missing_event_invitation_status_names,
    missing_group_role_names,
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
        role = GroupRole(name="admin")
        status = EventInvitationStatus(name="attending")
        db.session.add_all([user, role, status])
        db.session.commit()

        membership = Membership(user_id=user.id, role_id=role.id)
        invitation = EventInvitation(user_id=user.id, status_id=status.id)
        db.session.add_all([membership, invitation])
        db.session.commit()

        assert membership.user.id == user.id
        assert membership.role.name == "admin"
        assert invitation.status.name == "attending"


def test_group_membership_helpers(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]

        user = User(username="groupuser", email="groupuser@example.com", password_hash="x")
        member_role = GroupRole(name="member")
        pending_role = GroupRole(name="pending")
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


def test_group_join_uses_role_names(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]

        user = User(username="joiner", email="joiner@example.com", password_hash="x")
        member_role = GroupRole(name="member")
        pending_role = GroupRole(name="pending")
        public_group = Group(name="Open Group", shortname="open-group", invite_only=False)
        private_group = Group(name="Private Group", shortname="private-group", invite_only=True)

        db.session.add_all([user, member_role, pending_role, public_group, private_group])
        db.session.commit()

        public_group.join(user)
        private_group.join(user)
        db.session.commit()

        public_participation = public_group.get_membership(user)
        private_participation = private_group.get_membership(user)

        assert public_participation is not None
        assert private_participation is not None
        assert public_participation.role.name == "member"
        assert private_participation.role.name == "pending"


def test_group_membership_transition_helpers(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]

        admin_role = GroupRole(name="admin")
        member_role = GroupRole(name="member")
        pending_role = GroupRole(name="pending")
        user = User(username="transition", email="transition@example.com", password_hash="x")
        group = Group(name="Helpers Group", shortname="helpers-group", invite_only=True)

        db.session.add_all([admin_role, member_role, pending_role, user, group])
        db.session.commit()

        pending_membership = group.ensure_membership(user, role_name="pending")
        db.session.commit()

        assert group.is_pending(user) is True
        assert group.is_active_member(user) is False
        assert pending_membership.role.name == "pending"

        member_membership = group.approve_membership(user)
        db.session.commit()

        assert member_membership.id == pending_membership.id
        assert group.is_active_member(user) is True
        assert group.has_role(user, "member") is True

        admin_membership = group.promote_to_admin(user)
        db.session.commit()

        assert admin_membership.id == pending_membership.id
        assert group.is_admin(user) is True


def test_group_ensure_membership_rejects_unknown_role(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]

        user = User(username="unknown-role", email="unknown-role@example.com", password_hash="x")
        group = Group(name="Unknown Role Group", shortname="unknown-role-group")
        db.session.add_all([user, group])
        db.session.commit()

        try:
            group.ensure_membership(user, role_name="vip")
        except ValueError as exc:
            assert "Unknown group role" in str(exc)
        else:
            raise AssertionError("expected ValueError for unknown group role")


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


def test_group_can_own_external_links(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]

        group = Group(name="Link Club", shortname="link-club")
        link = GroupExternalUrl(
            group=group,
            name="Main Site",
            type="website",
            url="https://example.com",
        )

        db.session.add_all([group, link])
        db.session.commit()

        assert link.group is not None
        assert link.group.name == "Link Club"
        assert group.links[0].url == "https://example.com"


def test_group_can_own_dues_schedule(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]

        group = Group(name="Dues Club", shortname="dues-club")
        dues = GroupDues(
            group=group,
            name="Annual Membership",
            description="Full year membership",
            fee=99.0,
            duration=365,
        )

        db.session.add_all([group, dues])
        db.session.commit()

        assert dues.group is not None
        assert dues.group.name == "Dues Club"
        assert group.dues_schedule[0].fee == 99.0


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


def test_event_can_own_fee_definitions(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]

        event = Event(name="Paid Fondo")
        fee = EventFee(
            event=event,
            name="General Admission",
            description="Standard entry",
            fee=45.0,
            duration=1,
        )

        db.session.add_all([event, fee])
        db.session.commit()

        assert fee.event is not None
        assert fee.event.name == "Paid Fondo"
        assert event.fees[0].fee == 45.0


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


def test_event_invitation_status_constants_are_complete() -> None:
    assert EVENT_INVITATION_STATUS_NAMES == (
        "invited",
        "attending",
        "interested",
        "not_attending",
    )


def test_group_role_constants_are_complete() -> None:
    assert GROUP_ROLE_NAMES == ("admin", "member", "pending")


def test_missing_event_invitation_status_names() -> None:
    missing = missing_event_invitation_status_names(["invited", "attending"])
    assert missing == ["interested", "not_attending"]


def test_missing_group_role_names() -> None:
    missing = missing_group_role_names(["admin"])
    assert missing == ["member", "pending"]


def test_event_invitation_status_lookup_by_name(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        status = EventInvitationStatus(name="interested")
        db.session.add(status)
        db.session.commit()

        found = EventInvitationStatus.by_name("interested")
        assert found is not None
        assert found.id == status.id


def test_group_role_lookup_by_name(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        role = GroupRole(name="member")
        db.session.add(role)
        db.session.commit()

        found = GroupRole.by_name("member")
        assert found is not None
        assert found.id == role.id


def test_membership_role_helpers(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]

        admin = GroupRole(name="admin")
        member = GroupRole(name="member")
        pending = GroupRole(name="pending")
        user = User(username="roles", email="roles@example.com", password_hash="x")
        membership = Membership(user=user, role=member)
        db.session.add_all([admin, member, pending, user, membership])
        db.session.commit()

        assert membership.is_member() is True
        assert membership.is_pending() is False
        assert membership.is_admin() is False

        membership.set_role_by_name("pending")
        db.session.commit()
        assert membership.is_pending() is True

        membership.set_role_by_name("admin")
        db.session.commit()
        assert membership.is_admin() is True


def test_membership_set_role_by_name_rejects_unknown_role(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]

        member = GroupRole(name="member")
        user = User(username="badrole", email="badrole@example.com", password_hash="x")
        membership = Membership(user=user, role=member)
        db.session.add_all([member, user, membership])
        db.session.commit()

        try:
            membership.set_role_by_name("vip")
        except ValueError as exc:
            assert "Unknown group role" in str(exc)
        else:
            raise AssertionError("expected ValueError for unknown role")


def test_event_ensure_participation_by_status_name(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]

        invited = EventInvitationStatus(name="invited")
        attending = EventInvitationStatus(name="attending")
        user = User(username="rsvp", email="rsvp@example.com", password_hash="x")
        event = Event(name="Town Ride")
        db.session.add_all([invited, attending, user, event])
        db.session.commit()

        created = event.ensure_participation(user, status_name="invited")
        db.session.add(created)
        db.session.commit()

        assert created.status.name == "invited"
        assert event.get_participation(user) is not None

        updated = event.ensure_participation(user, status_name="attending")
        db.session.commit()

        assert updated.id == created.id
        assert updated.status.name == "attending"


def test_event_ensure_participation_rejects_unknown_status(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        user = User(username="oops", email="oops@example.com", password_hash="x")
        event = Event(name="Mystery Ride")
        db.session.add_all([user, event])
        db.session.commit()

        try:
            event.ensure_participation(user, status_name="maybe")
        except ValueError as exc:
            assert "Unknown event invitation status" in str(exc)
        else:
            raise AssertionError("expected ValueError for unknown status")


def test_event_rsvp_helpers_use_canonical_status_names(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]

        statuses = [
            EventInvitationStatus(name="invited"),
            EventInvitationStatus(name="interested"),
            EventInvitationStatus(name="attending"),
            EventInvitationStatus(name="not_attending"),
        ]
        user = User(username="rsvp-helpers", email="rsvp-helpers@example.com", password_hash="x")
        event = Event(name="Summer Rally")
        db.session.add_all([*statuses, user, event])
        db.session.commit()

        invitation = event.invite(user)
        db.session.commit()
        assert invitation.status.name == "invited"

        invitation = event.mark_interested(user)
        db.session.commit()
        assert invitation.status.name == "interested"

        invitation = event.mark_attending(user)
        db.session.commit()
        assert invitation.status.name == "attending"

        invitation = event.mark_not_attending(user)
        db.session.commit()
        assert invitation.status.name == "not_attending"
