from flask import Flask
from flask.testing import FlaskClient

from app.bootstrap import ensure_canonical_lookup_rows
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
from app.services import (
    add_event_fee,
    add_group_dues,
    add_group_link,
    attach_calendar,
    attach_segment_to_route,
    create_activity,
    create_event,
    create_group,
    create_point_of_interest,
    create_route,
    create_segment,
    ensure_group_membership,
    list_activities,
    list_points_of_interest,
    list_routes,
    list_segments,
    set_rsvp,
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


def test_ensure_canonical_lookup_rows(app: Flask, database: None) -> None:
    with app.app_context():
        result = ensure_canonical_lookup_rows()

        assert result["event_invitation_statuses"] == list(EVENT_INVITATION_STATUS_NAMES)
        assert result["group_roles"] == list(GROUP_ROLE_NAMES)
        assert EventInvitationStatus.by_name("attending") is not None
        assert GroupRole.by_name("member") is not None


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


def test_group_services_create_and_extend_group(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        ensure_canonical_lookup_rows()
        user = User(username="service-group", email="service-group@example.com", password_hash="x")
        db.session.add(user)
        db.session.commit()

        group = create_group(name="Service Group", shortname="service-group", invite_only=True)
        membership = ensure_group_membership(group, user)
        link = add_group_link(group, name="Club Site", url="https://example.com/groups/service")
        dues = add_group_dues(
            group,
            name="Annual Dues",
            fee=55.0,
            duration=365,
            description="Service layer dues",
        )

        assert membership.role.name == "pending"
        assert group.links[0].id == link.id
        assert group.dues_schedule[0].id == dues.id


def test_event_services_create_and_extend_event(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        ensure_canonical_lookup_rows()
        owner = User(username="service-owner", email="service-owner@example.com", password_hash="x")
        attendee = User(
            username="service-attendee",
            email="service-attendee@example.com",
            password_hash="x",
        )
        group = Group(name="Service Calendar Group", shortname="service-calendar-group")
        calendar = Calendar(name="Service Calendar", group=group, type="club")
        db.session.add_all([owner, attendee, group, calendar])
        db.session.commit()

        event = create_event(
            name="Service Event",
            owner=owner,
            description="Thin service event",
            town="Oakland",
            state="CA",
        )
        attach_calendar(event, calendar)
        participation = set_rsvp(event, attendee, status_name="attending")
        fee = add_event_fee(
            event,
            name="Service Entry",
            fee=25.0,
            duration=1,
            description="Single-day entry",
        )

        assert event.calendars[0].id == calendar.id
        assert participation.status.name == "attending"
        assert event.fees[0].id == fee.id
        assert event.route_id is None
        assert event.activity_id is None


def test_event_can_link_route_and_activity(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        athlete = User(
            username="event-athlete",
            email="event-athlete@example.com",
            password_hash="x",
        )
        owner = User(
            username="event-owner",
            email="event-owner@example.com",
            password_hash="x",
        )
        db.session.add_all([athlete, owner])
        db.session.commit()

        route = create_route(name="Event Route")
        activity = create_activity(athlete=athlete, route=route, name="Event Activity")
        event = create_event(
            name="Linked Event",
            owner=owner,
            route=route,
            activity=activity,
        )

        assert event.route_id == route.id
        assert event.activity_id == activity.id


def test_api_endpoints_exercise_group_and_event_flows(
    app: Flask,
    client: FlaskClient,
    database: None,
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        owner = User(username="api-owner", email="api-owner@example.com", password_hash="x")
        attendee = User(
            username="api-attendee",
            email="api-attendee@example.com",
            password_hash="x",
        )
        group = Group(name="API Calendar Group", shortname="api-calendar-group")
        calendar = Calendar(name="API Calendar", group=group, type="club")
        db.session.add_all([owner, attendee, group, calendar])
        db.session.commit()
        owner_id = owner.id
        attendee_id = attendee.id
        calendar_id = calendar.id

    bootstrap_response = client.post("/api/bootstrap/lookup-rows", json={})
    assert bootstrap_response.status_code == 200
    assert bootstrap_response.get_json() == {
        "event_invitation_statuses": list(EVENT_INVITATION_STATUS_NAMES),
        "group_roles": list(GROUP_ROLE_NAMES),
    }

    group_response = client.post(
        "/api/groups",
        json={
            "name": "API Group",
            "shortname": "api-group",
            "invite_only": True,
        },
    )
    assert group_response.status_code == 201
    group_payload = group_response.get_json()
    assert group_payload == {
        "id": group_payload["id"],
        "name": "API Group",
        "shortname": "api-group",
        "invite_only": True,
        "private": False,
    }
    group_id = group_payload["id"]

    membership_response = client.post(
        f"/api/groups/{group_id}/memberships",
        json={"user_id": owner_id},
    )
    assert membership_response.status_code == 201
    assert membership_response.get_json() == {
        "group_id": group_id,
        "membership_id": membership_response.get_json()["membership_id"],
        "user_id": owner_id,
        "role_name": "pending",
    }

    link_response = client.post(
        f"/api/groups/{group_id}/links",
        json={
            "name": "API Site",
            "type": "website",
            "url": "https://example.com/api-group",
        },
    )
    assert link_response.status_code == 201
    assert link_response.get_json() == {
        "group_id": group_id,
        "link_id": link_response.get_json()["link_id"],
        "name": "API Site",
        "type": "website",
        "url": "https://example.com/api-group",
    }

    dues_response = client.post(
        f"/api/groups/{group_id}/dues",
        json={
            "name": "API Dues",
            "fee": 42.5,
            "duration": 365,
            "description": "API-created dues",
        },
    )
    assert dues_response.status_code == 201
    assert dues_response.get_json() == {
        "group_id": group_id,
        "dues_id": dues_response.get_json()["dues_id"],
        "name": "API Dues",
        "fee": 42.5,
        "duration": 365,
    }

    event_response = client.post(
        "/api/events",
        json={
            "name": "API Event",
            "owner_id": owner_id,
            "description": "Created through the thin API",
            "town": "Berkeley",
            "state": "CA",
        },
    )
    assert event_response.status_code == 201
    event_payload = event_response.get_json()
    assert event_payload == {
        "id": event_payload["id"],
        "name": "API Event",
        "owner_id": owner_id,
        "route_id": None,
        "activity_id": None,
        "private": False,
        "town": "Berkeley",
        "state": "CA",
    }
    event_id = event_payload["id"]

    calendar_link_response = client.post(
        f"/api/events/{event_id}/calendar-links",
        json={"calendar_id": calendar_id},
    )
    assert calendar_link_response.status_code == 201
    assert calendar_link_response.get_json() == {
        "event_id": event_id,
        "calendar_ids": [calendar_id],
    }

    rsvp_response = client.post(
        f"/api/events/{event_id}/rsvps",
        json={"user_id": attendee_id, "status_name": "attending"},
    )
    assert rsvp_response.status_code == 201
    assert rsvp_response.get_json() == {
        "event_id": event_id,
        "participation_id": rsvp_response.get_json()["participation_id"],
        "user_id": attendee_id,
        "status_name": "attending",
    }

    fee_response = client.post(
        f"/api/events/{event_id}/fees",
        json={
            "name": "API Event Fee",
            "fee": 18.0,
            "duration": 1,
            "description": "API-created fee",
        },
    )
    assert fee_response.status_code == 201
    assert fee_response.get_json() == {
        "event_id": event_id,
        "fee_id": fee_response.get_json()["fee_id"],
        "name": "API Event Fee",
        "fee": 18.0,
        "duration": 1,
    }


def test_api_event_can_link_route_and_activity(
    app: Flask,
    client: FlaskClient,
    database: None,
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        owner = User(
            username="linked-event-owner",
            email="linked-event-owner@example.com",
            password_hash="x",
        )
        athlete = User(
            username="linked-event-athlete",
            email="linked-event-athlete@example.com",
            password_hash="x",
        )
        db.session.add_all([owner, athlete])
        db.session.commit()
        route = create_route(name="Linked API Route")
        activity = create_activity(athlete=athlete, route=route, name="Linked API Activity")
        owner_id = owner.id
        route_id = route.id
        activity_id = activity.id

    response = client.post(
        "/api/events",
        json={
            "name": "Linked API Event",
            "owner_id": owner_id,
            "route_id": route_id,
            "activity_id": activity_id,
        },
    )
    assert response.status_code == 201
    assert response.get_json() == {
        "id": response.get_json()["id"],
        "name": "Linked API Event",
        "owner_id": owner_id,
        "route_id": route_id,
        "activity_id": activity_id,
        "private": False,
        "town": None,
        "state": None,
    }


def test_point_of_interest_services_create_and_filter(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        owner = User(username="poi-owner", email="poi-owner@example.com", password_hash="x")
        other_user = User(username="poi-other", email="poi-other@example.com", password_hash="x")
        db.session.add_all([owner, other_user])
        db.session.commit()

        trailhead = create_point_of_interest(
            owner=owner,
            name="Redwood Trailhead",
            poi_type="trailhead",
            subtype="gravel",
            lat=37.8,
            lon=-122.2,
            description="Forest start",
            icon="tree",
        )
        create_point_of_interest(
            owner=other_user,
            name="Coffee Stop",
            poi_type="cafe",
            lat=37.81,
            lon=-122.21,
        )

        owned_points = list_points_of_interest(owner=owner)

        assert len(owned_points) == 1
        assert owned_points[0].id == trailhead.id
        assert owned_points[0].type == "trailhead"


def test_api_point_of_interest_endpoints(app: Flask, client: FlaskClient, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        owner = User(username="api-poi", email="api-poi@example.com", password_hash="x")
        db.session.add(owner)
        db.session.commit()
        owner_id = owner.id

    create_response = client.post(
        "/api/points-of-interest",
        json={
            "owner_id": owner_id,
            "name": "Summit Viewpoint",
            "type": "viewpoint",
            "subtype": "scenic",
            "lat": 37.91,
            "lon": -122.51,
            "url": "https://example.com/viewpoint",
            "description": "Panoramic ridge stop",
            "icon": "binoculars",
        },
    )
    assert create_response.status_code == 201
    assert create_response.get_json() == {
        "id": create_response.get_json()["id"],
        "owner_id": owner_id,
        "name": "Summit Viewpoint",
        "type": "viewpoint",
        "subtype": "scenic",
        "lat": 37.91,
        "lon": -122.51,
        "url": "https://example.com/viewpoint",
        "description": "Panoramic ridge stop",
        "icon": "binoculars",
    }

    list_response = client.get(f"/api/points-of-interest?owner_id={owner_id}")
    assert list_response.status_code == 200
    assert list_response.get_json() == {
        "items": [
            {
                "id": create_response.get_json()["id"],
                "owner_id": owner_id,
                "name": "Summit Viewpoint",
                "type": "viewpoint",
                "subtype": "scenic",
                "lat": 37.91,
                "lon": -122.51,
                "url": "https://example.com/viewpoint",
                "description": "Panoramic ridge stop",
                "icon": "binoculars",
            }
        ]
    }


def test_route_services_create_and_filter(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        creator = User(
            username="route-creator",
            email="route-creator@example.com",
            password_hash="x",
        )
        other_user = User(
            username="route-other",
            email="route-other@example.com",
            password_hash="x",
        )
        db.session.add_all([creator, other_user])
        db.session.commit()

        route = create_route(
            creator=creator,
            name="Redwood Loop",
            desc="Mixed terrain training route",
            private=False,
            length=54.2,
            elevation_gain=1200.0,
            route_type="ride",
            subtype="mixed",
            start_latitude=37.82,
            start_longitude=-122.24,
            end_latitude=37.82,
            end_longitude=-122.24,
            city="Oakland",
            state="CA",
        )
        create_route(
            creator=other_user,
            name="City Spin",
            route_type="ride",
        )

        creator_routes = list_routes(creator=creator)

        assert len(creator_routes) == 1
        assert creator_routes[0].id == route.id
        assert creator_routes[0].length == 54.2


def test_api_route_endpoints(app: Flask, client: FlaskClient, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        creator = User(username="api-route", email="api-route@example.com", password_hash="x")
        db.session.add(creator)
        db.session.commit()
        creator_id = creator.id

    create_response = client.post(
        "/api/routes",
        json={
            "creator_id": creator_id,
            "name": "Marin Headlands",
            "desc": "Classic coastal loop",
            "private": False,
            "duration": 10800.0,
            "length": 67.5,
            "elevation_gain": 1800.0,
            "type": "ride",
            "subtype": "road",
            "src": "manual",
            "src_id": "route-123",
            "start_latitude": 37.83,
            "start_longitude": -122.48,
            "end_latitude": 37.83,
            "end_longitude": -122.48,
            "city": "Sausalito",
            "state": "CA",
            "country": "USA",
            "address": "Bridgeway",
            "map_thumbnail": "https://example.com/maps/marin.png",
        },
    )
    assert create_response.status_code == 201
    assert create_response.get_json() == {
        "id": create_response.get_json()["id"],
        "creator_id": creator_id,
        "name": "Marin Headlands",
        "desc": "Classic coastal loop",
        "private": False,
        "duration": 10800.0,
        "length": 67.5,
        "elevation_gain": 1800.0,
        "type": "ride",
        "subtype": "road",
        "src": "manual",
        "src_id": "route-123",
        "start_latitude": 37.83,
        "start_longitude": -122.48,
        "end_latitude": 37.83,
        "end_longitude": -122.48,
        "city": "Sausalito",
        "state": "CA",
        "country": "USA",
        "address": "Bridgeway",
        "map_thumbnail": "https://example.com/maps/marin.png",
    }

    list_response = client.get(f"/api/routes?creator_id={creator_id}")
    assert list_response.status_code == 200
    assert list_response.get_json() == {
        "items": [
            {
                "id": create_response.get_json()["id"],
                "creator_id": creator_id,
                "name": "Marin Headlands",
                "desc": "Classic coastal loop",
                "private": False,
                "duration": 10800.0,
                "length": 67.5,
                "elevation_gain": 1800.0,
                "type": "ride",
                "subtype": "road",
                "src": "manual",
                "src_id": "route-123",
                "start_latitude": 37.83,
                "start_longitude": -122.48,
                "end_latitude": 37.83,
                "end_longitude": -122.48,
                "city": "Sausalito",
                "state": "CA",
                "country": "USA",
                "address": "Bridgeway",
                "map_thumbnail": "https://example.com/maps/marin.png",
            }
        ]
    }


def test_segment_services_create_and_attach_to_route(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        creator = User(
            username="segment-route-creator",
            email="segment-route-creator@example.com",
            password_hash="x",
        )
        db.session.add(creator)
        db.session.commit()

        route = create_route(creator=creator, name="Connector Route")
        segment = create_segment(
            name="Climb Segment",
            length=4.8,
            elevation_gain=420.0,
            segment_type="climb",
            track_hash="seg-climb-001",
        )
        attach_segment_to_route(route, segment)

        segments = list_segments()

        assert len(segments) == 1
        assert segments[0].id == segment.id
        assert route.segments[0].id == segment.id
        assert segment.routes[0].id == route.id


def test_api_segment_endpoints(app: Flask, client: FlaskClient, database: None) -> None:
    create_response = client.post(
        "/api/segments",
        json={
            "name": "Coastal Descent",
            "desc": "Fast downhill toward the bay",
            "duration": 720.0,
            "length": 6.4,
            "elevation_gain": 40.0,
            "elevation_loss": 310.0,
            "elev_high": 280.0,
            "elev_low": 12.0,
            "rating": 4.5,
            "grade": -4.2,
            "type": "descent",
            "subtype": "road",
            "src": "manual",
            "src_id": "segment-123",
            "src_url": "https://example.com/segments/123",
            "start_latitude": 37.9,
            "start_longitude": -122.6,
            "end_latitude": 37.84,
            "end_longitude": -122.5,
            "track_hash": "segment-123-hash",
            "track_maxspeed": 18.7,
        },
    )
    assert create_response.status_code == 201
    assert create_response.get_json() == {
        "id": create_response.get_json()["id"],
        "name": "Coastal Descent",
        "desc": "Fast downhill toward the bay",
        "duration": 720.0,
        "length": 6.4,
        "elevation_gain": 40.0,
        "elevation_loss": 310.0,
        "elev_high": 280.0,
        "elev_low": 12.0,
        "rating": 4.5,
        "grade": -4.2,
        "type": "descent",
        "subtype": "road",
        "src": "manual",
        "src_id": "segment-123",
        "src_url": "https://example.com/segments/123",
        "start_latitude": 37.9,
        "start_longitude": -122.6,
        "end_latitude": 37.84,
        "end_longitude": -122.5,
        "track_hash": "segment-123-hash",
        "track_maxspeed": 18.7,
    }

    list_response = client.get("/api/segments")
    assert list_response.status_code == 200
    assert list_response.get_json() == {
        "items": [
            {
                "id": create_response.get_json()["id"],
                "name": "Coastal Descent",
                "desc": "Fast downhill toward the bay",
                "duration": 720.0,
                "length": 6.4,
                "elevation_gain": 40.0,
                "elevation_loss": 310.0,
                "elev_high": 280.0,
                "elev_low": 12.0,
                "rating": 4.5,
                "grade": -4.2,
                "type": "descent",
                "subtype": "road",
                "src": "manual",
                "src_id": "segment-123",
                "src_url": "https://example.com/segments/123",
                "start_latitude": 37.9,
                "start_longitude": -122.6,
                "end_latitude": 37.84,
                "end_longitude": -122.5,
                "track_hash": "segment-123-hash",
                "track_maxspeed": 18.7,
            }
        ]
    }


def test_api_can_attach_segment_to_route(app: Flask, client: FlaskClient, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        creator = User(
            username="attach-route-creator",
            email="attach-route-creator@example.com",
            password_hash="x",
        )
        db.session.add(creator)
        db.session.commit()
        route = create_route(creator=creator, name="Attachment Route")
        segment = create_segment(name="Attachment Segment", track_hash="attach-segment-001")
        route_id = route.id
        segment_id = segment.id

    attach_response = client.post(
        f"/api/routes/{route_id}/segments",
        json={"segment_id": segment_id},
    )
    assert attach_response.status_code == 201
    assert attach_response.get_json() == {
        "route_id": route_id,
        "segment_ids": [segment_id],
    }


def test_activity_services_create_and_filter(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        athlete = User(
            username="activity-athlete",
            email="activity-athlete@example.com",
            password_hash="x",
        )
        other_athlete = User(
            username="activity-other",
            email="activity-other@example.com",
            password_hash="x",
        )
        db.session.add_all([athlete, other_athlete])
        db.session.commit()

        route = create_route(name="Training Route")
        activity = create_activity(
            athlete=athlete,
            route=route,
            name="Morning Ride",
            duration=5400.0,
            length=42.1,
            average_speed=27.2,
            activity_type="ride",
            src="manual",
            src_id="activity-001",
        )
        create_activity(
            athlete=other_athlete,
            name="Other Activity",
            activity_type="ride",
        )

        athlete_activities = list_activities(athlete=athlete)
        route_activities = list_activities(route=route)

        assert len(athlete_activities) == 1
        assert athlete_activities[0].id == activity.id
        assert len(route_activities) == 1
        assert route_activities[0].id == activity.id
        assert route_activities[0].route_id == route.id


def test_api_activity_endpoints(app: Flask, client: FlaskClient, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        athlete = User(
            username="api-activity-athlete",
            email="api-activity-athlete@example.com",
            password_hash="x",
        )
        db.session.add(athlete)
        db.session.commit()
        route = create_route(name="Activity API Route")
        athlete_id = athlete.id
        route_id = route.id

    create_response = client.post(
        "/api/activities",
        json={
            "athlete_id": athlete_id,
            "route_id": route_id,
            "name": "Lunch Spin",
            "desc": "Midday training block",
            "private": False,
            "photo_url": "https://example.com/activity.png",
            "duration": 3600.0,
            "length": 28.3,
            "elevation_gain": 510.0,
            "average_speed": 28.3,
            "max_speed": 52.1,
            "moving_time": 3400.0,
            "total_elevation_gain": 510.0,
            "elev_high": 440.0,
            "elev_low": 12.0,
            "type": "ride",
            "subtype": "road",
            "src": "manual",
            "src_id": "activity-123",
            "start_latitude": 37.78,
            "start_longitude": -122.42,
            "end_latitude": 37.78,
            "end_longitude": -122.42,
        },
    )
    assert create_response.status_code == 201
    assert create_response.get_json() == {
        "id": create_response.get_json()["id"],
        "athlete_id": athlete_id,
        "route_id": route_id,
        "name": "Lunch Spin",
        "desc": "Midday training block",
        "private": False,
        "photo_url": "https://example.com/activity.png",
        "duration": 3600.0,
        "length": 28.3,
        "elevation_gain": 510.0,
        "average_speed": 28.3,
        "max_speed": 52.1,
        "moving_time": 3400.0,
        "total_elevation_gain": 510.0,
        "elev_high": 440.0,
        "elev_low": 12.0,
        "type": "ride",
        "subtype": "road",
        "src": "manual",
        "src_id": "activity-123",
        "start_latitude": 37.78,
        "start_longitude": -122.42,
        "end_latitude": 37.78,
        "end_longitude": -122.42,
    }

    list_response = client.get(f"/api/activities?athlete_id={athlete_id}&route_id={route_id}")
    assert list_response.status_code == 200
    assert list_response.get_json() == {
        "items": [
            {
                "id": create_response.get_json()["id"],
                "athlete_id": athlete_id,
                "route_id": route_id,
                "name": "Lunch Spin",
                "desc": "Midday training block",
                "private": False,
                "photo_url": "https://example.com/activity.png",
                "duration": 3600.0,
                "length": 28.3,
                "elevation_gain": 510.0,
                "average_speed": 28.3,
                "max_speed": 52.1,
                "moving_time": 3400.0,
                "total_elevation_gain": 510.0,
                "elev_high": 440.0,
                "elev_low": 12.0,
                "type": "ride",
                "subtype": "road",
                "src": "manual",
                "src_id": "activity-123",
                "start_latitude": 37.78,
                "start_longitude": -122.42,
                "end_latitude": 37.78,
                "end_longitude": -122.42,
            }
        ]
    }
