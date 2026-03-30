from flask import Flask
from flask.testing import FlaskClient

from app.bootstrap import ensure_canonical_lookup_rows
from app.config import Config, TestConfig
from app.extensions import login_manager
from app.models import (
    EVENT_INVITATION_STATUS_NAMES,
    GROUP_ROLE_NAMES,
    Activity,
    Calendar,
    Event,
    EventFee,
    EventInvitation,
    EventInvitationStatus,
    Group,
    GroupDues,
    GroupExternalUrl,
    GroupRole,
    Image,
    Membership,
    PointOfInterest,
    Route,
    Segment,
    User,
    missing_event_invitation_status_names,
    missing_group_role_names,
)
from app.services import (
    add_event_fee,
    add_group_dues,
    add_group_link,
    add_route_link,
    attach_calendar,
    attach_image_to_event,
    attach_image_to_poi,
    attach_route_to_group,
    attach_segment_to_route,
    create_activity,
    create_event,
    create_group,
    create_image,
    create_point_of_interest,
    create_route,
    create_segment,
    ensure_group_membership,
    list_activities,
    list_images,
    list_points_of_interest,
    list_routes,
    list_segments,
    parse_search_types,
    rebuild_search_documents,
    search_documents,
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
        user = User(
            username="brett",
            email="brett@example.com",
            preference_tags=["fitness", "road"],
            tags=["climber", "coffee"],
            home_town="Oakland",
            home_state="CA",
            home_country="USA",
            home_gym="Lake Merritt",
            home_latlng="37.8044,-122.2711",
            geoll='{"type":"Point","coordinates":[-122.2711,37.8044]}',
        )
        user.set_password("secret123")
        db = app.extensions["sqlalchemy"]
        db.session.add(user)
        db.session.commit()

        assert user.check_password("secret123") is True
        token = user.get_reset_password_token()

        restored = User.verify_reset_password_token(token)
        assert restored is not None
        assert restored.id == user.id
        assert restored.preference_tags == ["fitness", "road"]
        assert restored.tags == ["climber", "coffee"]
        assert restored.home_town == "Oakland"
        assert restored.home_state == "CA"
        assert restored.home_country == "USA"
        assert restored.home_gym == "Lake Merritt"
        assert restored.home_latlng == "37.8044,-122.2711"
        assert restored.geoll == '{"type":"Point","coordinates":[-122.2711,37.8044]}'


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
        calendar = Calendar(name="Club Calendar", group=group, type="club", tags=["road", "club"])

        db.session.add_all([group, calendar])
        db.session.commit()

        assert calendar.group is not None
        assert calendar.group.name == "Calendar Club"
        assert group.calendars[0].name == "Club Calendar"
        assert group.calendars[0].tags == ["road", "club"]


def test_group_can_own_external_links(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]

        group = Group(name="Link Club", shortname="link-club")
        link = GroupExternalUrl(
            group=group,
            name="Main Site",
            type="website",
            url="https://example.com",
            tags=["official", "member-info"],
        )

        db.session.add_all([group, link])
        db.session.commit()

        assert link.group is not None
        assert link.group.name == "Link Club"
        assert group.links[0].url == "https://example.com"
        assert group.links[0].tags == ["official", "member-info"]


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
            tags=["annual", "member"],
        )

        db.session.add_all([group, dues])
        db.session.commit()

        assert dues.group is not None
        assert dues.group.name == "Dues Club"
        assert group.dues_schedule[0].fee == 99.0
        assert group.dues_schedule[0].tags == ["annual", "member"]


def test_group_can_link_routes(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]

        group = Group(name="Route Club", shortname="route-club")
        route = create_route(name="Club Route")
        db.session.add(group)
        db.session.commit()

        attach_route_to_group(group, route)

        assert group.routes[0].id == route.id
        assert route.groups[0].id == group.id


def test_route_can_own_external_links(app: Flask, database: None) -> None:
    with app.app_context():
        route = create_route(name="Linked Route")
        link = add_route_link(
            route,
            name="Ride Details",
            url="https://example.com/routes/linked",
        )

        assert route.links[0].id == link.id
        assert link.route is not None
        assert link.route.id == route.id


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
            tags=["entry", "general"],
        )

        db.session.add_all([event, fee])
        db.session.commit()

        assert fee.event is not None
        assert fee.event.name == "Paid Fondo"
        assert event.fees[0].fee == 45.0
        assert event.fees[0].tags == ["entry", "general"]


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


def test_trimmed_image_model_persists_relationships(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        photographer = User(
            username="photographer",
            email="photographer@example.com",
            password_hash="x",
        )
        group = Group(name="Image Group", shortname="image-group")
        segment = Segment(name="Image Segment")
        activity = Activity(name="Image Activity")
        db.session.add_all([photographer, group, segment, activity])
        db.session.commit()

        image = Image(
            img_medium="https://example.com/images/medium.jpg",
            img_thumb="https://example.com/images/thumb.jpg",
            title="Golden Hour",
            caption="Evening light",
            url="https://example.com/images/full.jpg",
            latlng="37.8,-122.2",
            geoll='{"type":"Point","coordinates":[-122.2,37.8]}',
            tags=["sunset", "featured"],
            photographer=photographer,
            group=group,
            segment=segment,
            activity=activity,
        )
        db.session.add(image)
        db.session.commit()

        assert image.photographer_id == photographer.id
        assert image.group_id == group.id
        assert image.segment_id == segment.id
        assert image.activity_id == activity.id
        assert image.geoll == '{"type":"Point","coordinates":[-122.2,37.8]}'
        assert image.tags == ["sunset", "featured"]
        assert segment.images[0].id == image.id
        assert activity.images[0].id == image.id


def test_image_services_create_and_filter(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        photographer = User(
            username="service-photographer",
            email="service-photographer@example.com",
            password_hash="x",
        )
        other = User(username="service-other", email="service-other@example.com", password_hash="x")
        group = Group(name="Image Service Group", shortname="image-service-group")
        segment = Segment(name="Image Service Segment")
        activity = Activity(name="Image Service Activity")
        db.session.add_all([photographer, other, group, segment, activity])
        db.session.commit()

        image = create_image(
            photographer=photographer,
            group=group,
            segment=segment,
            activity=activity,
            img_medium="https://example.com/service-medium.jpg",
            img_thumb="https://example.com/service-thumb.jpg",
            title="Service Image",
            geoll='{"type":"Point","coordinates":[-122.3,37.82]}',
            tags=["service", "cover"],
        )
        create_image(
            photographer=other,
            img_medium="https://example.com/other-medium.jpg",
            title="Other Image",
        )

        photographer_images = list_images(photographer=photographer)
        group_images = list_images(group=group)
        segment_images = list_images(segment=segment)
        activity_images = list_images(activity=activity)

        assert len(photographer_images) == 1
        assert photographer_images[0].id == image.id
        assert len(group_images) == 1
        assert group_images[0].id == image.id
        assert len(segment_images) == 1
        assert segment_images[0].id == image.id
        assert len(activity_images) == 1
        assert activity_images[0].id == image.id
        assert activity_images[0].geoll == '{"type":"Point","coordinates":[-122.3,37.82]}'
        assert activity_images[0].tags == ["service", "cover"]
        assert segment.images[0].id == image.id
        assert activity.images[0].id == image.id


def test_poi_can_link_images(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        owner = User(
            username="poi-image-owner",
            email="poi-image-owner@example.com",
            password_hash="x",
        )
        photographer = User(
            username="poi-image-photographer",
            email="poi-image-photographer@example.com",
            password_hash="x",
        )
        db.session.add_all([owner, photographer])
        db.session.commit()

        point = create_point_of_interest(
            owner=owner,
            name="POI Image Stop",
            poi_type="viewpoint",
            geoll='{"type":"Point","coordinates":[-122.45,37.86]}',
            tags=["scenic", "photo-stop"],
        )
        image = create_image(
            photographer=photographer,
            img_medium="https://example.com/poi/image.jpg",
            title="POI Image",
        )
        attach_image_to_poi(point, image)

        assert point.images[0].id == image.id
        assert image.pois[0].id == point.id
        assert point.tags == ["scenic", "photo-stop"]


def test_group_services_create_and_extend_group(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        ensure_canonical_lookup_rows()
        user = User(username="service-group", email="service-group@example.com", password_hash="x")
        hero_photo = Image(img_medium="https://example.com/groups/hero.jpg")
        db.session.add_all([user, hero_photo])
        db.session.commit()

        group = create_group(
            name="Service Group",
            shortname="service-group",
            invite_only=True,
            home_town="Oakland",
            home_state="CA",
            home_country="USA",
            geoll='{"type":"Point","coordinates":[-122.2711,37.8044]}',
            preference_tags=["community", "road"],
            tags=["featured", "east-bay"],
            rider_classes=["beginner", "intermediate"],
            ride_classes=["road", "gravel"],
            hero_photo=hero_photo,
        )
        membership = ensure_group_membership(group, user)
        link = add_group_link(
            group,
            name="Club Site",
            url="https://example.com/groups/service",
            tags=["official", "club"],
        )
        dues = add_group_dues(
            group,
            name="Annual Dues",
            fee=55.0,
            duration=365,
            description="Service layer dues",
            tags=["annual", "recurring"],
        )

        assert membership.role.name == "pending"
        assert group.links[0].id == link.id
        assert group.dues_schedule[0].id == dues.id
        assert link.tags == ["official", "club"]
        assert dues.tags == ["annual", "recurring"]
        assert group.preference_tags == ["community", "road"]
        assert group.tags == ["featured", "east-bay"]
        assert group.rider_classes == ["beginner", "intermediate"]
        assert group.ride_classes == ["road", "gravel"]
        assert group.home_latlng == "37.8044,-122.2711"
        assert group.geoll == '{"type":"Point","coordinates":[-122.2711,37.8044]}'
        assert group.hero_photo_id == hero_photo.id


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
            url="https://example.com/events/service-event",
            reg_url="https://example.com/events/service-event/register",
            photo_url="https://example.com/events/service-event.jpg",
            logo="https://example.com/events/service-logo.png",
            profile_photo="https://example.com/events/service-profile.png",
            notes="Bring lights for the return ride.",
            tags=["drop-ride", "night"],
            lat=37.8044,
            lon=-122.2711,
            town="Oakland",
            state="CA",
            country="USA",
        )
        attach_calendar(event, calendar)
        participation = set_rsvp(event, attendee, status_name="attending")
        fee = add_event_fee(
            event,
            name="Service Entry",
            fee=25.0,
            duration=1,
            description="Single-day entry",
            tags=["day-pass", "entry"],
        )
        image = create_image(
            photographer=owner,
            img_medium="https://example.com/events/service-image.jpg",
            title="Service Event Image",
        )
        attach_image_to_event(event, image)

        assert event.calendars[0].id == calendar.id
        assert participation.status.name == "attending"
        assert event.fees[0].id == fee.id
        assert event.route_id is None
        assert event.activity_id is None
        assert event.tags == ["drop-ride", "night"]
        assert fee.tags == ["day-pass", "entry"]
        assert event.latlng == "37.8044,-122.2711"
        assert event.geoll == '{"type":"Point","coordinates":[-122.2711,37.8044]}'
        assert event.images[0].id == image.id


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
        hero_photo = Image(img_medium="https://example.com/groups/api-hero.jpg")
        group = Group(name="API Calendar Group", shortname="api-calendar-group")
        calendar = Calendar(name="API Calendar", group=group, type="club")
        db.session.add_all([owner, attendee, hero_photo, group, calendar])
        db.session.commit()
        owner_id = owner.id
        attendee_id = attendee.id
        calendar_id = calendar.id
        hero_photo_id = hero_photo.id

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
            "home_town": "Berkeley",
            "home_state": "CA",
            "home_country": "USA",
            "home_latlng": "37.8715,-122.273",
            "home_add": "2000 Center St",
            "full_address": "2000 Center St, Berkeley, CA",
            "geoll": '{"type":"Point","coordinates":[-122.273,37.8715]}',
            "preference_tags": ["women", "road"],
            "tags": ["featured", "east-bay"],
            "rider_classes": ["novice", "advanced"],
            "ride_classes": ["road", "training"],
            "hero_photo_id": hero_photo_id,
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
        "home_town": "Berkeley",
        "home_state": "CA",
        "home_country": "USA",
        "home_latlng": "37.8715,-122.273",
        "home_add": "2000 Center St",
        "full_address": "2000 Center St, Berkeley, CA",
        "geoll": '{"type":"Point","coordinates":[-122.273,37.8715]}',
        "preference_tags": ["women", "road"],
        "tags": ["featured", "east-bay"],
        "rider_classes": ["novice", "advanced"],
        "ride_classes": ["road", "training"],
        "hero_photo_id": hero_photo_id,
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
            "tags": ["official", "join"],
            "url": "https://example.com/api-group",
        },
    )
    assert link_response.status_code == 201
    assert link_response.get_json() == {
        "group_id": group_id,
        "link_id": link_response.get_json()["link_id"],
        "name": "API Site",
        "type": "website",
        "tags": ["official", "join"],
        "url": "https://example.com/api-group",
    }

    dues_response = client.post(
        f"/api/groups/{group_id}/dues",
        json={
            "name": "API Dues",
            "fee": 42.5,
            "duration": 365,
            "description": "API-created dues",
            "tags": ["annual", "members"],
        },
    )
    assert dues_response.status_code == 201
    assert dues_response.get_json() == {
        "group_id": group_id,
        "dues_id": dues_response.get_json()["dues_id"],
        "name": "API Dues",
        "fee": 42.5,
        "duration": 365,
        "tags": ["annual", "members"],
    }

    image_create_response = client.post(
        "/api/images",
        json={
            "photographer_id": owner_id,
            "img_medium": "https://example.com/events/api-image.jpg",
            "title": "API Event Image",
            "tags": ["hero", "event"],
        },
    )
    assert image_create_response.status_code == 201
    image_id = image_create_response.get_json()["id"]

    event_response = client.post(
        "/api/events",
        json={
            "name": "API Event",
            "owner_id": owner_id,
            "description": "Created through the thin API",
            "url": "https://example.com/events/api-event",
            "reg_url": "https://example.com/events/api-event/register",
            "photo_url": "https://example.com/events/api-event.jpg",
            "logo": "https://example.com/events/api-logo.png",
            "profile_photo": "https://example.com/events/api-profile.png",
            "notes": "Meet ten minutes early.",
            "tags": ["drop-ride", "women"],
            "lat": 37.8715,
            "lon": -122.273,
            "town": "Berkeley",
            "state": "CA",
            "country": "USA",
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
        "description": "Created through the thin API",
        "url": "https://example.com/events/api-event",
        "reg_url": "https://example.com/events/api-event/register",
        "photo_url": "https://example.com/events/api-event.jpg",
        "logo": "https://example.com/events/api-logo.png",
        "profile_photo": "https://example.com/events/api-profile.png",
        "notes": "Meet ten minutes early.",
        "tags": ["drop-ride", "women"],
        "lat": 37.8715,
        "lon": -122.273,
        "town": "Berkeley",
        "state": "CA",
        "country": "USA",
        "latlng": "37.8715,-122.273",
        "geoll": '{"type":"Point","coordinates":[-122.273,37.8715]}',
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

    event_image_response = client.post(
        f"/api/events/{event_id}/images",
        json={"image_id": image_id},
    )
    assert event_image_response.status_code == 201
    assert event_image_response.get_json() == {
        "event_id": event_id,
        "image_ids": [image_id],
    }

    event_image_list_response = client.get(f"/api/events/{event_id}/images")
    assert event_image_list_response.status_code == 200
    assert event_image_list_response.get_json() == {
        "items": [
            {
                "id": image_id,
                "photographer_id": owner_id,
                "group_id": None,
                "segment_id": None,
                "activity_id": None,
                "img_small": None,
                "img_medium": "https://example.com/events/api-image.jpg",
                "img_large": None,
                "img_thumb": None,
                "alt_txt": None,
                "title": "API Event Image",
                "caption": None,
                "latlng": None,
                "geoll": None,
                "tags": ["hero", "event"],
                "url": None,
            }
        ]
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
            "tags": ["entry", "single-day"],
        },
    )
    assert fee_response.status_code == 201
    assert fee_response.get_json() == {
        "event_id": event_id,
        "fee_id": fee_response.get_json()["fee_id"],
        "name": "API Event Fee",
        "fee": 18.0,
        "duration": 1,
        "tags": ["entry", "single-day"],
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
        "description": None,
        "url": None,
        "reg_url": None,
        "photo_url": None,
        "logo": None,
        "profile_photo": None,
        "notes": None,
        "tags": None,
        "lat": None,
        "lon": None,
        "town": None,
        "state": None,
        "country": None,
        "latlng": None,
        "geoll": None,
    }


def test_api_group_can_attach_and_list_routes(
    app: Flask,
    client: FlaskClient,
    database: None,
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        group = Group(name="API Route Group", shortname="api-route-group")
        route = create_route(name="API Group Route")
        db.session.add(group)
        db.session.commit()
        group_id = group.id
        route_id = route.id

    attach_response = client.post(
        f"/api/groups/{group_id}/routes",
        json={"route_id": route_id},
    )
    assert attach_response.status_code == 201
    assert attach_response.get_json() == {
        "group_id": group_id,
        "route_ids": [route_id],
    }

    list_response = client.get(f"/api/groups/{group_id}/routes")
    assert list_response.status_code == 200
    assert list_response.get_json() == {
        "items": [
            {
                "id": route_id,
                "creator_id": None,
                "name": "API Group Route",
                "desc": None,
                "private": None,
                "duration": None,
                "length": None,
                "elevation_gain": None,
                "tags": None,
                "elevation_array": None,
                "type": None,
                "subtype": None,
                "src": None,
                "src_id": None,
                "start_latitude": None,
                "start_longitude": None,
                "end_latitude": None,
                "end_longitude": None,
                "summary_polyline": None,
                "full_track": None,
                "city": None,
                "state": None,
                "country": None,
                "address": None,
                "map_thumbnail": None,
            }
        ]
    }


def test_api_route_can_attach_and_list_links(
    app: Flask,
    client: FlaskClient,
    database: None,
) -> None:
    with app.app_context():
        route = create_route(name="API Linked Route")
        route_id = route.id

    attach_response = client.post(
        f"/api/routes/{route_id}/links",
        json={
            "name": "Route Site",
            "type": "website",
            "tags": ["beta", "cue-sheet"],
            "url": "https://example.com/routes/api-linked",
        },
    )
    assert attach_response.status_code == 201
    assert attach_response.get_json() == {
        "route_id": route_id,
        "link_id": attach_response.get_json()["link_id"],
        "name": "Route Site",
        "type": "website",
        "tags": ["beta", "cue-sheet"],
        "url": "https://example.com/routes/api-linked",
    }

    list_response = client.get(f"/api/routes/{route_id}/links")
    assert list_response.status_code == 200
    assert list_response.get_json() == {
        "items": [
            {
                "route_id": route_id,
                "link_id": attach_response.get_json()["link_id"],
                "name": "Route Site",
                "type": "website",
                "tags": ["beta", "cue-sheet"],
                "url": "https://example.com/routes/api-linked",
            }
        ]
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
            tags=["trailhead", "forest"],
            icon="tree",
        )
        create_point_of_interest(
            owner=other_user,
            name="Coffee Stop",
            poi_type="cafe",
            geoll='{"type":"Point","coordinates":[-122.21,37.81]}',
        )

        owned_points = list_points_of_interest(owner=owner)

        assert len(owned_points) == 1
        assert owned_points[0].id == trailhead.id
        assert owned_points[0].type == "trailhead"
        assert owned_points[0].tags == ["trailhead", "forest"]
        assert owned_points[0].geoll == '{"type":"Point","coordinates":[-122.2,37.8]}'


def test_api_point_of_interest_endpoints(app: Flask, client: FlaskClient, database: None) -> None:
    geoll = '{"type":"Point","coordinates":[-122.51,37.91]}'

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
            "geoll": geoll,
            "url": "https://example.com/viewpoint",
            "description": "Panoramic ridge stop",
            "tags": ["viewpoint", "photo-stop"],
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
        "geoll": geoll,
        "url": "https://example.com/viewpoint",
        "description": "Panoramic ridge stop",
        "tags": ["viewpoint", "photo-stop"],
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
                "geoll": geoll,
                "url": "https://example.com/viewpoint",
                "description": "Panoramic ridge stop",
                "tags": ["viewpoint", "photo-stop"],
                "icon": "binoculars",
            }
        ]
    }

    image_create_response = client.post(
        "/api/images",
        json={
            "photographer_id": owner_id,
            "img_medium": "https://example.com/poi/api-image.jpg",
            "title": "POI API Image",
        },
    )
    assert image_create_response.status_code == 201
    image_id = image_create_response.get_json()["id"]

    poi_image_response = client.post(
        f"/api/points-of-interest/{create_response.get_json()['id']}/images",
        json={"image_id": image_id},
    )
    assert poi_image_response.status_code == 201
    assert poi_image_response.get_json() == {
        "point_id": create_response.get_json()["id"],
        "image_ids": [image_id],
    }

    poi_image_list_response = client.get(
        f"/api/points-of-interest/{create_response.get_json()['id']}/images"
    )
    assert poi_image_list_response.status_code == 200
    assert poi_image_list_response.get_json() == {
        "items": [
            {
                "id": image_id,
                "photographer_id": owner_id,
                "group_id": None,
                "segment_id": None,
                "activity_id": None,
                "img_small": None,
                "img_medium": "https://example.com/poi/api-image.jpg",
                "img_large": None,
                "img_thumb": None,
                "alt_txt": None,
                "title": "POI API Image",
                "caption": None,
                "latlng": None,
                "geoll": None,
                "tags": None,
                "url": None,
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
            tags=["road", "climbing"],
            elevation_array=[32.0, 45.5, 128.2],
            route_type="ride",
            subtype="mixed",
            start_latitude=37.82,
            start_longitude=-122.24,
            end_latitude=37.82,
            end_longitude=-122.24,
            summary_polyline='{"type":"LineString","coordinates":[[-122.24,37.82],[-122.2,37.84]]}',
            full_track='{"type":"LineString","coordinates":[[-122.24,37.82,10],[-122.2,37.84,25]]}',
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
        assert creator_routes[0].tags == ["road", "climbing"]
        assert creator_routes[0].elevation_array == [32.0, 45.5, 128.2]
        assert creator_routes[0].summary_polyline is not None
        assert creator_routes[0].full_track is not None


def test_api_route_endpoints(app: Flask, client: FlaskClient, database: None) -> None:
    summary_polyline = '{"type":"LineString","coordinates":[[-122.48,37.83],[-122.45,37.85]]}'
    full_track = '{"type":"LineString","coordinates":[[-122.48,37.83,5],[-122.45,37.85,15]]}'

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
            "tags": ["coastal", "road"],
            "elevation_array": [0, 45.5, 120],
            "type": "ride",
            "subtype": "road",
            "src": "manual",
            "src_id": "route-123",
            "start_latitude": 37.83,
            "start_longitude": -122.48,
            "end_latitude": 37.83,
            "end_longitude": -122.48,
            "summary_polyline": summary_polyline,
            "full_track": full_track,
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
        "tags": ["coastal", "road"],
        "elevation_array": [0.0, 45.5, 120.0],
        "type": "ride",
        "subtype": "road",
        "src": "manual",
        "src_id": "route-123",
        "start_latitude": 37.83,
        "start_longitude": -122.48,
        "end_latitude": 37.83,
        "end_longitude": -122.48,
        "summary_polyline": summary_polyline,
        "full_track": full_track,
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
                "tags": ["coastal", "road"],
                "elevation_array": [0.0, 45.5, 120.0],
                "type": "ride",
                "subtype": "road",
                "src": "manual",
                "src_id": "route-123",
                "start_latitude": 37.83,
                "start_longitude": -122.48,
                "end_latitude": 37.83,
                "end_longitude": -122.48,
                "summary_polyline": summary_polyline,
                "full_track": full_track,
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
            elevation_array=[10.0, 55.5, 90.0],
            segment_type="climb",
            tags=["climb", "ocean"],
            summary_polyline='{"type":"LineString","coordinates":[[-122.3,37.8],[-122.28,37.82]]}',
            full_track='{"type":"LineString","coordinates":[[-122.3,37.8,20],[-122.28,37.82,110]]}',
            track_hash="seg-climb-001",
        )
        attach_segment_to_route(route, segment)

        segments = list_segments()

        assert len(segments) == 1
        assert segments[0].id == segment.id
        assert segments[0].elevation_array == [10.0, 55.5, 90.0]
        assert segments[0].tags == ["climb", "ocean"]
        assert segments[0].summary_polyline is not None
        assert segments[0].full_track is not None
        assert route.segments[0].id == segment.id
        assert segment.routes[0].id == route.id


def test_api_segment_endpoints(app: Flask, client: FlaskClient, database: None) -> None:
    summary_polyline = '{"type":"LineString","coordinates":[[-122.6,37.9],[-122.5,37.84]]}'
    full_track = '{"type":"LineString","coordinates":[[-122.6,37.9,50],[-122.5,37.84,12]]}'

    create_response = client.post(
        "/api/segments",
        json={
            "name": "Coastal Descent",
            "desc": "Fast downhill toward the bay",
            "duration": 720.0,
            "length": 6.4,
            "elevation_gain": 40.0,
            "elevation_array": [4, 20.5, 44],
            "elevation_loss": 310.0,
            "elev_high": 280.0,
            "elev_low": 12.0,
            "rating": 4.5,
            "grade": -4.2,
            "type": "descent",
            "subtype": "road",
            "tags": ["descent", "road"],
            "src": "manual",
            "src_id": "segment-123",
            "src_url": "https://example.com/segments/123",
            "start_latitude": 37.9,
            "start_longitude": -122.6,
            "end_latitude": 37.84,
            "end_longitude": -122.5,
            "summary_polyline": summary_polyline,
            "full_track": full_track,
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
        "elevation_array": [4.0, 20.5, 44.0],
        "elevation_loss": 310.0,
        "elev_high": 280.0,
        "elev_low": 12.0,
        "rating": 4.5,
        "grade": -4.2,
        "type": "descent",
        "subtype": "road",
        "tags": ["descent", "road"],
        "src": "manual",
        "src_id": "segment-123",
        "src_url": "https://example.com/segments/123",
        "start_latitude": 37.9,
        "start_longitude": -122.6,
        "end_latitude": 37.84,
        "end_longitude": -122.5,
        "summary_polyline": summary_polyline,
        "full_track": full_track,
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
                "elevation_array": [4.0, 20.5, 44.0],
                "elevation_loss": 310.0,
                "elev_high": 280.0,
                "elev_low": 12.0,
                "rating": 4.5,
                "grade": -4.2,
                "type": "descent",
                "subtype": "road",
                "tags": ["descent", "road"],
                "src": "manual",
                "src_id": "segment-123",
                "src_url": "https://example.com/segments/123",
                "start_latitude": 37.9,
                "start_longitude": -122.6,
                "end_latitude": 37.84,
                "end_longitude": -122.5,
                "summary_polyline": summary_polyline,
                "full_track": full_track,
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
            tags=["training", "endurance"],
            duration=5400.0,
            length=42.1,
            average_speed=27.2,
            activity_type="ride",
            src="manual",
            src_id="activity-001",
            summary_polyline='{"type":"LineString","coordinates":[[-122.42,37.78],[-122.38,37.8]]}',
            full_track='{"type":"LineString","coordinates":[[-122.42,37.78,8],[-122.38,37.8,22]]}',
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
        assert route_activities[0].tags == ["training", "endurance"]
        assert route_activities[0].summary_polyline is not None
        assert route_activities[0].full_track is not None


def test_api_activity_endpoints(app: Flask, client: FlaskClient, database: None) -> None:
    summary_polyline = '{"type":"LineString","coordinates":[[-122.42,37.78],[-122.39,37.8]]}'
    full_track = '{"type":"LineString","coordinates":[[-122.42,37.78,11],[-122.39,37.8,27]]}'

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
            "tags": ["tempo", "road"],
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
            "summary_polyline": summary_polyline,
            "full_track": full_track,
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
        "tags": ["tempo", "road"],
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
        "summary_polyline": summary_polyline,
        "full_track": full_track,
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
                "tags": ["tempo", "road"],
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
                "summary_polyline": summary_polyline,
                "full_track": full_track,
            }
        ]
    }


def test_api_image_endpoints(app: Flask, client: FlaskClient, database: None) -> None:
    geoll = '{"type":"Point","coordinates":[-122.41,37.78]}'

    with app.app_context():
        db = app.extensions["sqlalchemy"]
        photographer = User(
            username="api-photographer",
            email="api-photographer@example.com",
            password_hash="x",
        )
        group = Group(name="API Image Group", shortname="api-image-group")
        segment = Segment(name="API Image Segment")
        activity = Activity(name="API Image Activity")
        db.session.add_all([photographer, group, segment, activity])
        db.session.commit()
        photographer_id = photographer.id
        group_id = group.id
        segment_id = segment.id
        activity_id = activity.id

    create_response = client.post(
        "/api/images",
        json={
            "photographer_id": photographer_id,
            "group_id": group_id,
            "segment_id": segment_id,
            "activity_id": activity_id,
            "img_small": "https://example.com/api-small.jpg",
            "img_medium": "https://example.com/api-medium.jpg",
            "img_large": "https://example.com/api-large.jpg",
            "img_thumb": "https://example.com/api-thumb.jpg",
            "alt_txt": "Foggy overlook",
            "title": "API Image",
            "caption": "Morning marine layer",
            "latlng": "37.78,-122.41",
            "geoll": geoll,
            "tags": ["fog", "featured"],
            "url": "https://example.com/api-full.jpg",
        },
    )
    assert create_response.status_code == 201
    assert create_response.get_json() == {
        "id": create_response.get_json()["id"],
        "photographer_id": photographer_id,
        "group_id": group_id,
        "segment_id": segment_id,
        "activity_id": activity_id,
        "img_small": "https://example.com/api-small.jpg",
        "img_medium": "https://example.com/api-medium.jpg",
        "img_large": "https://example.com/api-large.jpg",
        "img_thumb": "https://example.com/api-thumb.jpg",
        "alt_txt": "Foggy overlook",
        "title": "API Image",
        "caption": "Morning marine layer",
        "latlng": "37.78,-122.41",
        "geoll": geoll,
        "tags": ["fog", "featured"],
        "url": "https://example.com/api-full.jpg",
    }

    list_response = client.get(
        f"/api/images?photographer_id={photographer_id}&group_id={group_id}&segment_id={segment_id}&activity_id={activity_id}"
    )
    assert list_response.status_code == 200
    assert list_response.get_json() == {
        "items": [
            {
                "id": create_response.get_json()["id"],
                "photographer_id": photographer_id,
                "group_id": group_id,
                "segment_id": segment_id,
                "activity_id": activity_id,
                "img_small": "https://example.com/api-small.jpg",
                "img_medium": "https://example.com/api-medium.jpg",
                "img_large": "https://example.com/api-large.jpg",
                "img_thumb": "https://example.com/api-thumb.jpg",
                "alt_txt": "Foggy overlook",
                "title": "API Image",
                "caption": "Morning marine layer",
                "latlng": "37.78,-122.41",
                "geoll": geoll,
                "tags": ["fog", "featured"],
                "url": "https://example.com/api-full.jpg",
            }
        ]
    }


def test_search_type_parser_normalizes_and_deduplicates() -> None:
    assert parse_search_types(["Route", "event", "route", "unknown", ""]) == ["route", "event"]


def test_search_rebuild_indexes_existing_domain_records(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        group = Group(
            name="East Bay Riders",
            shortname="east-bay-riders",
            about_blurb="Weekly community rides in Oakland",
            tags=["community", "road"],
            home_town="Oakland",
            home_state="CA",
        )
        route = Route(
            name="Redwood Climb",
            desc="Shaded climb through the redwoods",
            tags=["climb", "redwoods"],
            city="Oakland",
            state="CA",
        )
        event = Event(
            name="Sunrise Rollout",
            description="Early social ride from the lake",
            tags=["social", "road"],
            town="Oakland",
            state="CA",
        )
        point = PointOfInterest(
            name="Joaquin Miller Trailhead",
            description="Popular trailhead with parking",
            tags=["trailhead", "parking"],
            type="trailhead",
        )
        db.session.add_all([group, route, event, point])
        db.session.commit()

        indexed = rebuild_search_documents()
        results = search_documents(query="oakland road")

        assert indexed >= 4
        assert any(
            result.entity_type == "group" and result.title == "East Bay Riders"
            for result in results
        )
        assert any(
            result.entity_type == "event" and result.title == "Sunrise Rollout"
            for result in results
        )


def test_search_indexes_new_service_records(app: Flask, database: None) -> None:
    with app.app_context():
        route = create_route(
            name="Tilden Loop",
            desc="Scenic rolling route above Berkeley",
            tags=["scenic", "rolling"],
            city="Berkeley",
            state="CA",
        )
        segment = create_segment(
            name="Seaview Climb",
            desc="Steady fire road climb",
            tags=["climb", "gravel"],
        )
        point = create_point_of_interest(
            name="Inspiration Point",
            poi_type="viewpoint",
            description="Wide-open East Bay overlook",
            tags=["viewpoint", "sunset"],
        )

        route_results = search_documents(query="berkeley scenic", types=["route"])
        segment_results = search_documents(query="fire road climb", types=["segment"])
        poi_results = search_documents(query="overlook sunset", types=["point_of_interest"])

        assert [result.entity_id for result in route_results] == [route.id]
        assert [result.entity_id for result in segment_results] == [segment.id]
        assert [result.entity_id for result in poi_results] == [point.id]


def test_api_search_and_reindex_endpoints(app: Flask, client: FlaskClient, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        group = Group(
            name="Marin Gravel Crew",
            shortname="marin-gravel",
            about_blurb="Mixed-surface rides across Marin",
            tags=["gravel", "mixed-surface"],
            home_town="Mill Valley",
            home_state="CA",
        )
        event = Event(
            name="Bridge to Ridge",
            description="Big Marin climbing day",
            tags=["climbing", "marin"],
            town="Sausalito",
            state="CA",
        )
        db.session.add_all([group, event])
        db.session.commit()

    rebuild_response = client.post("/api/search/reindex", json={})
    assert rebuild_response.status_code == 200
    assert rebuild_response.get_json()["indexed"] >= 2

    search_response = client.get("/api/search?q=marin&type=group&type=event")
    assert search_response.status_code == 200
    payload = search_response.get_json()
    assert payload is not None
    assert {item["title"] for item in payload["items"]} == {
        "Bridge to Ridge",
        "Marin Gravel Crew",
    }
    assert {(item["entity_type"], item["location"]) for item in payload["items"]} == {
        ("event", "Sausalito, CA"),
        ("group", "Mill Valley, CA"),
    }

    limited_response = client.get("/api/search?q=marin&limit=1")
    assert limited_response.status_code == 200
    limited_payload = limited_response.get_json()
    assert limited_payload is not None
    assert len(limited_payload["items"]) == 1

    missing_query_response = client.get("/api/search")
    assert missing_query_response.status_code == 400


def test_search_updates_after_direct_model_edit(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        group = Group(
            name="Peninsula Paceline",
            shortname="peninsula-paceline",
            home_town="Redwood City",
            tags=["road"],
        )
        db.session.add(group)
        db.session.commit()

        group.name = "Peninsula Gravel Collective"
        group.tags = ["gravel", "community"]
        db.session.commit()

        results = search_documents(query="gravel collective", types=["group"])

        assert [result.entity_id for result in results] == [group.id]
        assert results[0].tags == ["gravel", "community"]


def test_search_removes_documents_after_delete(app: Flask, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        point = PointOfInterest(
            name="Hidden Overlook",
            description="Quiet viewpoint above the bay",
            tags=["viewpoint"],
            type="viewpoint",
        )
        db.session.add(point)
        db.session.commit()

        result_ids = [result.entity_id for result in search_documents(query="hidden overlook")]
        assert result_ids == [point.id]

        db.session.delete(point)
        db.session.commit()

        assert search_documents(query="hidden overlook") == []


def test_admin_search_page_renders_results(app: Flask, client: FlaskClient, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        group = Group(
            name="North Bay Climbers",
            shortname="north-bay-climbers",
            about_blurb="Steep road rides around Fairfax",
            tags=["climbing", "road"],
            home_town="Fairfax",
            home_state="CA",
        )
        route = Route(
            name="Bolinas Ridge Loop",
            desc="Mixed surface route over the ridge",
            tags=["gravel", "ridge"],
            city="Fairfax",
            state="CA",
        )
        db.session.add_all([group, route])
        db.session.commit()

    response = client.get("/admin/search?q=fairfax&type=group&type=route&limit=5")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Admin Search" in html
    assert "North Bay Climbers" in html
    assert "Bolinas Ridge Loop" in html
    assert "Fairfax, CA" in html


def test_admin_search_page_handles_empty_state(client: FlaskClient, database: None) -> None:
    response = client.get("/admin/search")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Start with a name, place, description fragment, or tag." in html


def test_admin_search_page_links_to_detail_views(
    app: Flask, client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        event = Event(
            name="Summit Rollout",
            description="Morning start into the hills",
            tags=["climb"],
            town="Berkeley",
            state="CA",
        )
        db.session.add(event)
        db.session.commit()
        event_id = event.id

    response = client.get("/admin/search?q=summit")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert f"/admin/events/{event_id}" in html


def test_admin_group_detail_page_renders(app: Flask, client: FlaskClient, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        group = Group(
            name="East Bay Dirt",
            shortname="east-bay-dirt",
            about_blurb="Community gravel rides and route swaps",
            tags=["gravel", "community"],
            home_town="Oakland",
            home_state="CA",
        )
        db.session.add(group)
        db.session.commit()
        group_id = group.id

    response = client.get(f"/admin/groups/{group_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "East Bay Dirt" in html
    assert "Community gravel rides and route swaps" in html
    assert "Oakland, CA" in html


def test_admin_route_detail_page_renders(app: Flask, client: FlaskClient, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        route = Route(
            name="Skyline Traverse",
            desc="Long ridge route with mixed climbing",
            tags=["ridge", "climb"],
            city="Oakland",
            state="CA",
            length=54.2,
        )
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    response = client.get(f"/admin/routes/{route_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Skyline Traverse" in html
    assert "Long ridge route with mixed climbing" in html
    assert "54.20" in html


def test_admin_group_edit_page_updates_group_and_search(
    app: Flask, client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        group = Group(
            name="North Shore Road",
            shortname="north-shore-road",
            about_blurb="Road rides by the water",
            tags=["road"],
            home_town="Richmond",
            home_state="CA",
        )
        db.session.add(group)
        db.session.commit()
        group_id = group.id

    response = client.post(
        f"/admin/groups/{group_id}/edit",
        data={
            "name": "North Shore Gravel",
            "shortname": "north-shore-gravel",
            "about_blurb": "Mixed-surface rides by the water",
            "contact": "hello@example.com",
            "home_town": "Albany",
            "home_state": "CA",
            "tags": "gravel, community",
            "preference_tags": "mixed-surface",
            "invite_only": "true",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "North Shore Gravel" in html
    assert "Mixed-surface rides by the water" in html
    assert "Albany, CA" in html

    with app.app_context():
        db = app.extensions["sqlalchemy"]
        updated_group = db.session.get(Group, group_id)
        assert updated_group is not None
        assert updated_group.name == "North Shore Gravel"
        assert updated_group.tags == ["gravel", "community"]
        search_hits = search_documents(query="north shore gravel", types=["group"])
        assert [result.entity_id for result in search_hits] == [group_id]


def test_admin_route_edit_page_updates_route_and_search(
    app: Flask, client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        route = Route(
            name="Old Ridge Line",
            desc="Steady rolling route",
            tags=["road"],
            city="Berkeley",
            state="CA",
            length=32.0,
        )
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    response = client.post(
        f"/admin/routes/{route_id}/edit",
        data={
            "name": "New Ridge Line",
            "desc": "Steady rolling gravel route",
            "type": "gravel",
            "subtype": "mixed-surface",
            "length": "41.5",
            "elevation_gain": "2100",
            "city": "Oakland",
            "state": "CA",
            "tags": "gravel, ridge",
            "elevation_array": "100, 220, 315",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "New Ridge Line" in html
    assert "Steady rolling gravel route" in html
    assert "41.50" in html

    with app.app_context():
        db = app.extensions["sqlalchemy"]
        updated_route = db.session.get(Route, route_id)
        assert updated_route is not None
        assert updated_route.type == "gravel"
        assert updated_route.tags == ["gravel", "ridge"]
        assert updated_route.elevation_array == [100.0, 220.0, 315.0]
        search_hits = search_documents(query="new ridge line", types=["route"])
        assert [result.entity_id for result in search_hits] == [route_id]


def test_admin_event_edit_page_updates_event_and_search(
    app: Flask, client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        route = Route(name="Connector Route")
        activity = Activity(name="Warmup Activity")
        event = Event(
            name="Sunset Meetup",
            description="Neighborhood spin",
            tags=["social"],
            town="El Cerrito",
            state="CA",
        )
        db.session.add_all([route, activity, event])
        db.session.commit()
        event_id = event.id
        route_id = route.id
        activity_id = activity.id

    response = client.post(
        f"/admin/events/{event_id}/edit",
        data={
            "name": "Sunset Gravel Meetup",
            "description": "Neighborhood mixed-surface spin",
            "primary_activity": "Cycling",
            "type": "ride",
            "subtype": "social",
            "route_id": str(route_id),
            "activity_id": str(activity_id),
            "town": "Albany",
            "state": "CA",
            "tags": "gravel, social",
            "private": "true",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Sunset Gravel Meetup" in html
    assert "Neighborhood mixed-surface spin" in html
    assert "Albany, CA" in html

    with app.app_context():
        db = app.extensions["sqlalchemy"]
        updated_event = db.session.get(Event, event_id)
        assert updated_event is not None
        assert updated_event.private is True
        assert updated_event.route_id == route_id
        assert updated_event.activity_id == activity_id
        assert updated_event.tags == ["gravel", "social"]
        search_hits = search_documents(query="sunset gravel meetup", types=["event"])
        assert [result.entity_id for result in search_hits] == [event_id]


def test_admin_dashboard_renders_counts_and_recent_records(
    app: Flask, client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        group = Group(name="Marin Dawn Patrol", shortname="marin-dawn-patrol")
        route = Route(name="Pine Mountain Figure Eight")
        event = Event(name="Breakfast Rollout")
        db.session.add_all([group, route, event])
        db.session.commit()

    response = client.get("/admin")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Control room for the rebuilt domain." in html
    assert "Marin Dawn Patrol" in html
    assert "Pine Mountain Figure Eight" in html
    assert "Breakfast Rollout" in html
    assert "/admin/groups/new" in html
    assert "/admin/routes/new" in html
    assert "/admin/events/new" in html


def test_admin_group_create_page_creates_group_and_search_document(
    app: Flask, client: FlaskClient, database: None
) -> None:
    response = client.post(
        "/admin/groups/new",
        data={
            "name": "Golden Gate Rollers",
            "shortname": "golden-gate-rollers",
            "home_town": "San Francisco",
            "home_state": "CA",
            "tags": "road, community",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Golden Gate Rollers" in html
    assert "San Francisco, CA" in html

    with app.app_context():
        hits = search_documents(query="golden gate rollers", types=["group"])
        assert len(hits) == 1


def test_admin_route_create_page_creates_route_and_search_document(
    app: Flask, client: FlaskClient, database: None
) -> None:
    response = client.post(
        "/admin/routes/new",
        data={
            "name": "Wildcat Figure Eight",
            "desc": "Climbing-heavy loop across the hills",
            "type": "road",
            "city": "Berkeley",
            "state": "CA",
            "tags": "climb, hills",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Wildcat Figure Eight" in html
    assert "Climbing-heavy loop across the hills" in html

    with app.app_context():
        hits = search_documents(query="wildcat figure eight", types=["route"])
        assert len(hits) == 1


def test_admin_event_create_page_creates_event_and_search_document(
    app: Flask, client: FlaskClient, database: None
) -> None:
    response = client.post(
        "/admin/events/new",
        data={
            "name": "Sunday Harbor Meetup",
            "description": "Coffee spin along the water",
            "primary_activity": "Cycling",
            "type": "ride",
            "town": "San Francisco",
            "state": "CA",
            "tags": "coffee, social",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Sunday Harbor Meetup" in html
    assert "Coffee spin along the water" in html
    assert "San Francisco, CA" in html

    with app.app_context():
        hits = search_documents(query="sunday harbor meetup", types=["event"])
        assert len(hits) == 1
