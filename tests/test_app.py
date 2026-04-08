from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import select

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


def _create_test_user(
    app: Flask,
    *,
    username: str,
    email: str,
    password: str = "secret123",
    site_admin: bool = False,
    active: bool = True,
) -> int:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        user = User(
            username=username,
            email=email,
            active=active,
            site_admin=site_admin,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


def test_index_route(client: FlaskClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.get_json() == {"message": "explor_codex is ready"}


def test_health_route(client: FlaskClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_public_landing_route_renders(client: FlaskClient, database: None) -> None:
    response = client.get("/landing")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "More ride planning, less tool-switching." in html
    assert "Find the next ride faster." in html


def test_public_discover_route_renders_results(
    app: Flask, client: FlaskClient, database: None
) -> None:
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

    response = client.get("/discover?q=fairfax&type=group&type=route&limit=5")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Browse the rebuilt domain like a product, not a database." in html
    assert "North Bay Climbers" in html
    assert "Bolinas Ridge Loop" in html
    assert 'href="/routes/' in html
    assert "Log in to inspect" in html


def test_public_discover_hides_login_prompts_for_authenticated_user(
    app: Flask, client: FlaskClient, database: None
) -> None:
    user_id = _create_test_user(
        app,
        username="discover-user",
        email="discover@example.com",
        site_admin=False,
    )
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response = client.get("/discover?q=marin")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Log in for deeper access" not in html
    assert "Log in to inspect" not in html


def test_public_routes_route_renders_browser_page(
    app: Flask, client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        group = Group(name="Marin Dirt Collective", shortname="marin-dirt-collective")
        route = Route(
            name="Mt. Tam North Loop",
            desc="Big mixed-terrain route with ocean views and fire-road climbing.",
            tags=["favorite", "gravel"],
            type="ride",
            subtype="mixed terrain",
            length=68400.0,
            elevation_gain=1580.0,
            duration=245.0,
            city="Mill Valley",
            state="CA",
            country="USA",
            start_latitude=37.906,
            start_longitude=-122.596,
            end_latitude=37.929,
            end_longitude=-122.629,
        )
        route.groups.append(group)
        event = Event(name="Saturday Tam Rollout", route=route)
        db.session.add_all([group, route, event])
        db.session.commit()

    response = client.get("/routes")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Browse routes with the map and list moving together." in html
    assert "Mt. Tam North Loop" in html
    assert "Nearby" in html
    assert "Full database" in html
    assert "More filters" in html
    assert "/segments" in html
    assert "Showing up to 30 of" in html
    assert "Viewport " not in html


def test_public_segments_route_renders_browser_page(
    app: Flask, client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        route = Route(name="Skyline Route")
        segment = Segment(
            name="West Ridge Kick",
            desc="Short but decisive climb that shapes the rest of the day.",
            tags=["featured", "climb"],
            type="climb",
            subtype="ridge",
            length=4200.0,
            elevation_gain=410.0,
            duration=28.0,
            start_latitude=37.401,
            start_longitude=-122.201,
            end_latitude=37.418,
            end_longitude=-122.188,
        )
        segment.routes.append(route)
        db.session.add_all([route, segment])
        db.session.commit()

    response = client.get("/segments")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Browse segments like the defining efforts they are." in html
    assert "West Ridge Kick" in html
    assert "Map-first discovery" in html
    assert "Routes" in html
    assert "Viewport " not in html


def test_public_route_browser_shows_linked_title_and_card_image_for_admin(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        route = Route(
            name="Marsh Loop",
            map_thumbnail="https://images.example.com/marsh-loop.jpg",
            start_latitude=37.7,
            start_longitude=-122.4,
            end_latitude=37.8,
            end_longitude=-122.3,
        )
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    response = admin_client.get("/routes")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert f'href="/admin/routes/{route_id}"' in html
    assert "marsh-loop.jpg" in html


def test_public_route_browser_links_titles_for_signed_out_users(
    app: Flask, client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        route = Route(
            name="Public Route",
            start_latitude=37.7,
            start_longitude=-122.4,
            end_latitude=37.8,
            end_longitude=-122.3,
        )
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    response = client.get("/routes")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert f'href="/routes/{route_id}"' in html


def test_public_route_detail_route_renders(app: Flask, client: FlaskClient, database: None) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        route = Route(
            name="Tam Detail Loop",
            desc="A real public detail page for browse traffic.",
            type="ride",
            subtype="mixed terrain",
            city="Mill Valley",
            state="CA",
            start_latitude=37.7,
            start_longitude=-122.4,
            end_latitude=37.8,
            end_longitude=-122.3,
        )
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    response = client.get(f"/routes/{route_id}")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Tam Detail Loop" in html
    assert "Browse more routes" in html


def test_public_segment_detail_route_renders(
    app: Flask, client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        segment = Segment(
            name="Public Segment Detail",
            desc="A public landing page for a defining effort.",
            type="climb",
            subtype="ridge",
            start_latitude=37.4,
            start_longitude=-122.2,
            end_latitude=37.41,
            end_longitude=-122.18,
        )
        db.session.add(segment)
        db.session.commit()
        segment_id = segment.id

    response = client.get(f"/segments/{segment_id}")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Public Segment Detail" in html
    assert "Browse more segments" in html


def test_public_route_browser_truncates_long_description(
    app: Flask, client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        route = Route(
            name="Long Story Loop",
            desc=(
                "This route starts gently through the flats before turning into a long, "
                "winding climb above the reservoir with several overlooks, a rougher ridge "
                "section, and a fast return that keeps unfolding well past a short teaser."
            ),
            start_latitude=37.7,
            start_longitude=-122.4,
            end_latitude=37.8,
            end_longitude=-122.3,
        )
        db.session.add(route)
        db.session.commit()

    response = client.get("/api/browser/routes?limit=30")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    item = next(entry for entry in payload["items"] if entry["title"] == "Long Story Loop")
    assert len(item["description"]) <= 200
    assert item["description"].endswith("...")


def test_palette_link_hidden_for_non_admin(app: Flask, database: None) -> None:
    anon_response = app.test_client().get("/routes")

    assert anon_response.status_code == 200
    assert 'href="/palette"' not in anon_response.get_data(as_text=True)


def test_public_routes_route_caps_payload_to_thirty_records(
    app: Flask, client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        for index in range(35):
            db.session.add(
                Route(
                    name=f"Route {index}",
                    start_latitude=37.0 + index / 1000,
                    start_longitude=-122.0 - index / 1000,
                )
            )
        db.session.commit()

    response = client.get("/routes")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Showing up to 30 of 35 total routes" in html
    assert "Route 34" in html
    assert "Route 5" in html
    assert "Route 4" not in html
    assert "Route 0" not in html


def test_public_route_browser_api_filters_by_viewport_club_event_and_terrain(
    app: Flask, client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        target_group = Group(name="Target Club", shortname="target-club")
        other_group = Group(name="Other Club", shortname="other-club")
        target_route = Route(
            name="Marin Gravel Ribbon",
            tags=["favorite", "gravel"],
            type="ride",
            subtype="gravel",
            start_latitude=37.90,
            start_longitude=-122.60,
            end_latitude=37.94,
            end_longitude=-122.56,
            summary_polyline='{"type":"LineString","coordinates":[[-122.60,37.90],[-122.56,37.94]]}',
        )
        target_route.groups.append(target_group)
        other_route = Route(
            name="Road Spin",
            tags=["road"],
            type="ride",
            subtype="road",
            start_latitude=37.70,
            start_longitude=-122.40,
            end_latitude=37.72,
            end_longitude=-122.36,
            summary_polyline='{"type":"LineString","coordinates":[[-122.40,37.70],[-122.36,37.72]]}',
        )
        other_route.groups.append(other_group)
        db.session.add_all(
            [
                target_group,
                other_group,
                target_route,
                other_route,
                Event(name="Club Rollout", route=target_route),
            ]
        )
        db.session.commit()
        group_id = target_group.id

    response = client.get(
        f"/api/browser/routes?club_id={group_id}&eventful_only=true&terrain=gravel"
        "&min_lat=37.85&max_lat=37.96&min_lng=-122.65&max_lng=-122.50&limit=20"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total_matching"] == 1
    assert [item["title"] for item in payload["items"]] == ["Marin Gravel Ribbon"]


def test_public_segment_browser_api_filters_by_viewport_club_event_and_terrain(
    app: Flask, client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        group = Group(name="Segment Club", shortname="segment-club")
        route = Route(name="Cliff Road")
        route.groups.append(group)
        event = Event(name="Cliff Day", route=route)
        target_segment = Segment(
            name="West Ridge Wall",
            tags=["featured", "climb"],
            type="climb",
            subtype="ridge",
            start_latitude=37.50,
            start_longitude=-122.30,
            end_latitude=37.52,
            end_longitude=-122.28,
            summary_polyline='{"type":"LineString","coordinates":[[-122.30,37.50],[-122.28,37.52]]}',
        )
        target_segment.routes.append(route)
        other_segment = Segment(
            name="Valley Drag",
            tags=["flat"],
            type="road",
            subtype="valley",
            start_latitude=36.90,
            start_longitude=-121.90,
            end_latitude=36.92,
            end_longitude=-121.88,
            summary_polyline='{"type":"LineString","coordinates":[[-121.90,36.90],[-121.88,36.92]]}',
        )
        db.session.add_all([group, route, event, target_segment, other_segment])
        db.session.commit()
        group_id = group.id

    response = client.get(
        f"/api/browser/segments?club_id={group_id}&eventful_only=true&terrain=ridge"
        "&min_lat=37.45&max_lat=37.55&min_lng=-122.35&max_lng=-122.20&limit=20"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total_matching"] == 1
    assert [item["title"] for item in payload["items"]] == ["West Ridge Wall"]


def test_public_route_browser_api_supports_offset_pagination(
    app: Flask,
    client: FlaskClient,
    database: None,
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        for index in range(6):
            db.session.add(
                Route(
                    name=f"Paged Route {index}",
                    start_latitude=37.70 + index / 1000,
                    start_longitude=-122.40 - index / 1000,
                    summary_polyline=(
                        '{"type":"LineString","coordinates":[[-122.40,37.70],[-122.39,37.71]]}'
                    ),
                )
            )
        db.session.commit()

    response = client.get("/api/browser/routes?limit=2&offset=2&sort=length")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["limit"] == 2
    assert payload["offset"] == 2
    assert len(payload["items"]) == 2


def test_public_browser_area_search_returns_matching_locations(
    app: Flask, client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        db.session.add(
            Route(
                name="Capital Loop",
                city="Sacramento",
                state="CA",
                country="USA",
                start_latitude=38.57,
                start_longitude=-121.49,
                end_latitude=38.59,
                end_longitude=-121.45,
            )
        )
        db.session.add(
            Event(
                name="Cap City Ride",
                town="Sacramento",
                state="CA",
                country="USA",
                lat=38.58,
                lon=-121.48,
            )
        )
        db.session.commit()

    response = client.get("/api/browser/areas?q=sacra")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["items"]
    assert payload["items"][0]["label"] == "Sacramento, CA, USA"


def test_public_routes_route_hides_zero_club_and_event_counts(
    app: Flask, client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        db.session.add(
            Route(
                name="Solo Route",
                start_latitude=37.8,
                start_longitude=-122.4,
                end_latitude=37.81,
                end_longitude=-122.39,
            )
        )
        db.session.commit()

    response = client.get("/routes")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "0 clubs" not in html
    assert "0 events" not in html


def test_palette_route_renders_token_table(client: FlaskClient, database: None) -> None:
    response = client.get("/palette")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "See the design tokens before they disappear into the UI." in html
    assert "--warm-accent" in html
    assert "rgba(44, 102, 143, 0.12)" in html
    assert "Shadow and radius values listed alongside the palette." in html


def test_app_factory_enables_testing_config(app: Flask) -> None:
    assert app.testing is True


def test_app_registers_sqlalchemy_extension(app: Flask) -> None:
    assert "sqlalchemy" in app.extensions


def test_test_config_uses_in_memory_sqlite() -> None:
    assert TestConfig.SQLALCHEMY_DATABASE_URI == "sqlite+pysqlite:///:memory:"


def test_test_config_disables_csrf() -> None:
    assert TestConfig.WTF_CSRF_ENABLED is False


def test_auth_forms_render_csrf_tokens(client: FlaskClient, database: None) -> None:
    login_response = client.get("/auth/login")
    signup_response = client.get("/auth/signup")

    assert login_response.status_code == 200
    assert signup_response.status_code == 200
    assert 'name="csrf_token"' in login_response.get_data(as_text=True)
    assert 'name="csrf_token"' in signup_response.get_data(as_text=True)


def test_admin_edit_form_and_logout_render_csrf_tokens(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        group = Group(name="CSRF Club", shortname="csrf-club")
        db.session.add(group)
        db.session.commit()
        group_id = group.id

    edit_response = admin_client.get(f"/admin/groups/{group_id}/edit")
    dashboard_response = admin_client.get("/admin")

    assert edit_response.status_code == 200
    assert dashboard_response.status_code == 200
    assert 'name="csrf_token"' in edit_response.get_data(as_text=True)
    assert 'name="csrf_token"' in dashboard_response.get_data(as_text=True)


def test_json_api_routes_remain_usable_when_csrf_is_enabled(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    app.config["WTF_CSRF_ENABLED"] = True

    response = admin_client.post("/api/search/reindex", json={})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert "indexed" in payload


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


def test_signup_creates_first_site_admin(client: FlaskClient, app: Flask, database: None) -> None:
    response = client.post(
        "/auth/signup",
        data={
            "username": "founder",
            "email": "founder@example.com",
            "firstname": "Founding",
            "lastname": "Admin",
            "password": "secret123",
            "password_confirm": "secret123",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "site admin access is enabled" in html
    assert "founder@example.com" in html

    with app.app_context():
        db = app.extensions["sqlalchemy"]
        user = db.session.scalar(select(User).where(User.username == "founder"))
        assert user is not None
        assert user.site_admin is True


def test_login_and_logout_flow(client: FlaskClient, app: Flask, database: None) -> None:
    _create_test_user(app, username="login-user", email="login@example.com", site_admin=False)

    login_response = client.post(
        "/auth/login",
        data={"identity": "login-user", "password": "secret123"},
        follow_redirects=True,
    )
    assert login_response.status_code == 200
    login_html = login_response.get_data(as_text=True)
    assert "Welcome back" in login_html
    assert "login@example.com" in login_html

    logout_response = client.post("/auth/logout", follow_redirects=True)
    assert logout_response.status_code == 200
    logout_html = logout_response.get_data(as_text=True)
    assert "You have been logged out." in logout_html
    assert "Log in" in logout_html


def test_password_reset_request_and_reset_flow(
    client: FlaskClient, app: Flask, database: None
) -> None:
    _create_test_user(app, username="reset-user", email="reset@example.com")

    request_response = client.post(
        "/auth/password-reset",
        data={"email": "reset@example.com"},
        follow_redirects=True,
    )
    assert request_response.status_code == 200
    request_html = request_response.get_data(as_text=True)
    assert "/auth/password-reset/" in request_html
    assert "Email Preview" in request_html
    assert "reset@example.com" in request_html

    with app.app_context():
        outbox = app.extensions["email_outbox"]
        assert len(outbox) == 1
        assert outbox[0]["to"] == "reset@example.com"

    with app.app_context():
        db = app.extensions["sqlalchemy"]
        user = db.session.scalar(select(User).where(User.email == "reset@example.com"))
        assert user is not None
        token = user.get_reset_password_token()

    reset_response = client.post(
        f"/auth/password-reset/{token}",
        data={"password": "newsecret123", "password_confirm": "newsecret123"},
        follow_redirects=True,
    )
    assert reset_response.status_code == 200
    reset_html = reset_response.get_data(as_text=True)
    assert "Password updated." in reset_html

    login_response = client.post(
        "/auth/login",
        data={"identity": "reset@example.com", "password": "newsecret123"},
        follow_redirects=True,
    )
    assert login_response.status_code == 200
    assert "Welcome back" in login_response.get_data(as_text=True)


def test_account_edit_flow_updates_profile(client: FlaskClient, app: Flask, database: None) -> None:
    user_id = _create_test_user(app, username="profile-user", email="profile@example.com")
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response = client.post(
        "/auth/account/edit",
        data={
            "username": "profile-user",
            "email": "profile-updated@example.com",
            "firstname": "Profile",
            "lastname": "Updated",
            "units": "imperial",
            "home_town": "Oakland",
            "home_state": "CA",
            "tags": "road, coffee",
            "preference_tags": "community",
            "password": "",
            "password_confirm": "",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Account saved." in html
    assert "profile-updated@example.com" in html

    with app.app_context():
        db = app.extensions["sqlalchemy"]
        user = db.session.get(User, user_id)
        assert user is not None
        assert user.email == "profile-updated@example.com"
        assert user.firstname == "Profile"
        assert user.lastname == "Updated"
        assert user.units == "imperial"
        assert user.tags == ["road", "coffee"]


def test_admin_routes_require_login(client: FlaskClient, database: None) -> None:
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_non_admin_user_gets_forbidden_on_admin_route(
    client: FlaskClient, app: Flask, database: None
) -> None:
    user_id = _create_test_user(app, username="member-user", email="member@example.com")
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 403


def test_api_post_requires_site_admin(client: FlaskClient, database: None) -> None:
    response = client.post(
        "/api/groups",
        json={"name": "Unauthorized", "shortname": "unauthorized"},
    )
    assert response.status_code == 401
    assert response.get_json() == {"error": "authentication required"}


def test_non_admin_user_gets_forbidden_on_api_post(
    client: FlaskClient, app: Flask, database: None
) -> None:
    user_id = _create_test_user(app, username="api-member", email="api-member@example.com")
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response = client.post(
        "/api/groups",
        json={"name": "Blocked", "shortname": "blocked"},
    )
    assert response.status_code == 403
    assert response.get_json() == {"error": "site admin access required"}


def test_admin_user_pages_support_create_and_edit(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    create_response = admin_client.post(
        "/admin/users/new",
        data={
            "username": "ops-user",
            "email": "ops@example.com",
            "firstname": "Ops",
            "lastname": "User",
            "active": "true",
            "site_admin": "true",
            "password": "secret123",
            "password_confirm": "secret123",
        },
        follow_redirects=True,
    )
    assert create_response.status_code == 200
    create_html = create_response.get_data(as_text=True)
    assert "User created." in create_html
    assert "ops@example.com" in create_html

    with app.app_context():
        db = app.extensions["sqlalchemy"]
        user = db.session.scalar(select(User).where(User.username == "ops-user"))
        assert user is not None
        user_id = user.id

    list_response = admin_client.get("/admin/users")
    assert list_response.status_code == 200
    assert "ops@example.com" in list_response.get_data(as_text=True)

    edit_response = admin_client.post(
        f"/admin/users/{user_id}/edit",
        data={
            "username": "ops-user",
            "email": "ops@example.com",
            "firstname": "Updated",
            "lastname": "Operator",
            "account_type": "moderator",
            "active": "true",
            "site_admin": "true",
            "password": "",
            "password_confirm": "",
        },
        follow_redirects=True,
    )
    assert edit_response.status_code == 200
    edit_html = edit_response.get_data(as_text=True)
    assert "User saved." in edit_html
    assert "Updated Operator" in edit_html


def test_admin_image_create_and_edit_flow(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    with app.app_context():
        photographer_id = _create_test_user(app, username="img-photog", email="img@example.com")

    create_response = admin_client.post(
        "/admin/images/new",
        data={
            "photographer_id": str(photographer_id),
            "title": "Harbor Shot",
            "img_medium": "https://example.com/harbor.jpg",
            "tags": "featured, harbor",
        },
        follow_redirects=True,
    )
    assert create_response.status_code == 200
    assert "Image created." in create_response.get_data(as_text=True)

    with app.app_context():
        db = app.extensions["sqlalchemy"]
        image = db.session.scalar(select(Image).where(Image.title == "Harbor Shot"))
        assert image is not None
        image_id = image.id

    edit_response = admin_client.post(
        f"/admin/images/{image_id}/edit",
        data={
            "photographer_id": str(photographer_id),
            "title": "Harbor Shot Revised",
            "img_medium": "https://example.com/harbor-revised.jpg",
            "tags": "featured, revised",
        },
        follow_redirects=True,
    )
    assert edit_response.status_code == 200
    assert "Image saved." in edit_response.get_data(as_text=True)

    detail_response = admin_client.get(f"/admin/images/{image_id}")
    assert detail_response.status_code == 200
    detail_html = detail_response.get_data(as_text=True)
    assert "Open original" in detail_html
    assert "https://example.com/harbor-revised.jpg" in detail_html

    new_page_response = admin_client.get("/admin/images/new")
    assert new_page_response.status_code == 200
    new_page_html = new_page_response.get_data(as_text=True)
    assert 'list="photographer_id-options"' in new_page_html


def test_admin_link_create_and_edit_flow(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        group = Group(name="Link Group", shortname="link-group")
        db.session.add(group)
        db.session.commit()
        group_id = group.id

    create_response = admin_client.post(
        "/admin/links/new",
        data={
            "group_id": str(group_id),
            "name": "Club Site",
            "url": "https://example.com/club",
            "type": "website",
            "tags": "official",
        },
        follow_redirects=True,
    )
    assert create_response.status_code == 200
    assert "Link created." in create_response.get_data(as_text=True)

    with app.app_context():
        db = app.extensions["sqlalchemy"]
        link = db.session.scalar(
            select(GroupExternalUrl).where(GroupExternalUrl.name == "Club Site")
        )
        assert link is not None
        link_id = link.id

    edit_response = admin_client.post(
        f"/admin/links/{link_id}/edit",
        data={
            "group_id": str(group_id),
            "name": "Club Site Updated",
            "url": "https://example.com/club-updated",
            "type": "website",
            "tags": "official, updated",
        },
        follow_redirects=True,
    )
    assert edit_response.status_code == 200
    assert "Link saved." in edit_response.get_data(as_text=True)


def test_admin_dues_create_and_edit_flow(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        group = Group(name="Dues Group", shortname="dues-group")
        db.session.add(group)
        db.session.commit()
        group_id = group.id

    create_response = admin_client.post(
        "/admin/dues/new",
        data={
            "group_id": str(group_id),
            "name": "Annual Dues",
            "fee": "49.5",
            "duration": "365",
            "tags": "annual",
        },
        follow_redirects=True,
    )
    assert create_response.status_code == 200
    assert "Dues created." in create_response.get_data(as_text=True)

    with app.app_context():
        db = app.extensions["sqlalchemy"]
        dues = db.session.scalar(select(GroupDues).where(GroupDues.name == "Annual Dues"))
        assert dues is not None
        dues_id = dues.id

    edit_response = admin_client.post(
        f"/admin/dues/{dues_id}/edit",
        data={
            "group_id": str(group_id),
            "name": "Annual Dues Updated",
            "fee": "59.0",
            "duration": "365",
            "tags": "annual, updated",
        },
        follow_redirects=True,
    )
    assert edit_response.status_code == 200
    assert "Dues saved." in edit_response.get_data(as_text=True)


def test_admin_fee_create_and_edit_flow(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        event = Event(name="Fee Event")
        db.session.add(event)
        db.session.commit()
        event_id = event.id

    create_response = admin_client.post(
        "/admin/fees/new",
        data={
            "event_id": str(event_id),
            "name": "Entry Fee",
            "fee": "15.0",
            "duration": "1",
            "tags": "entry",
        },
        follow_redirects=True,
    )
    assert create_response.status_code == 200
    assert "Fee created." in create_response.get_data(as_text=True)

    with app.app_context():
        db = app.extensions["sqlalchemy"]
        fee = db.session.scalar(select(EventFee).where(EventFee.name == "Entry Fee"))
        assert fee is not None
        fee_id = fee.id

    edit_response = admin_client.post(
        f"/admin/fees/{fee_id}/edit",
        data={
            "event_id": str(event_id),
            "name": "Entry Fee Updated",
            "fee": "18.0",
            "duration": "1",
            "tags": "entry, updated",
        },
        follow_redirects=True,
    )
    assert edit_response.status_code == 200
    assert "Fee saved." in edit_response.get_data(as_text=True)


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
    admin_client: FlaskClient,
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

    bootstrap_response = admin_client.post("/api/bootstrap/lookup-rows", json={})
    assert bootstrap_response.status_code == 200
    assert bootstrap_response.get_json() == {
        "event_invitation_statuses": list(EVENT_INVITATION_STATUS_NAMES),
        "group_roles": list(GROUP_ROLE_NAMES),
    }

    group_response = admin_client.post(
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

    membership_response = admin_client.post(
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

    link_response = admin_client.post(
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

    dues_response = admin_client.post(
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

    image_create_response = admin_client.post(
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

    event_response = admin_client.post(
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

    calendar_link_response = admin_client.post(
        f"/api/events/{event_id}/calendar-links",
        json={"calendar_id": calendar_id},
    )
    assert calendar_link_response.status_code == 201
    assert calendar_link_response.get_json() == {
        "event_id": event_id,
        "calendar_ids": [calendar_id],
    }

    event_image_response = admin_client.post(
        f"/api/events/{event_id}/images",
        json={"image_id": image_id},
    )
    assert event_image_response.status_code == 201
    assert event_image_response.get_json() == {
        "event_id": event_id,
        "image_ids": [image_id],
    }

    event_image_list_response = admin_client.get(f"/api/events/{event_id}/images")
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

    rsvp_response = admin_client.post(
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

    fee_response = admin_client.post(
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
    admin_client: FlaskClient,
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

    response = admin_client.post(
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
    admin_client: FlaskClient,
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

    attach_response = admin_client.post(
        f"/api/groups/{group_id}/routes",
        json={"route_id": route_id},
    )
    assert attach_response.status_code == 201
    assert attach_response.get_json() == {
        "group_id": group_id,
        "route_ids": [route_id],
    }

    list_response = admin_client.get(f"/api/groups/{group_id}/routes")
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
    admin_client: FlaskClient,
    database: None,
) -> None:
    with app.app_context():
        route = create_route(name="API Linked Route")
        route_id = route.id

    attach_response = admin_client.post(
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

    list_response = admin_client.get(f"/api/routes/{route_id}/links")
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


def test_api_point_of_interest_endpoints(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    geoll = '{"type":"Point","coordinates":[-122.51,37.91]}'

    with app.app_context():
        db = app.extensions["sqlalchemy"]
        owner = User(username="api-poi", email="api-poi@example.com", password_hash="x")
        db.session.add(owner)
        db.session.commit()
        owner_id = owner.id

    create_response = admin_client.post(
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

    list_response = admin_client.get(f"/api/points-of-interest?owner_id={owner_id}")
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

    image_create_response = admin_client.post(
        "/api/images",
        json={
            "photographer_id": owner_id,
            "img_medium": "https://example.com/poi/api-image.jpg",
            "title": "POI API Image",
        },
    )
    assert image_create_response.status_code == 201
    image_id = image_create_response.get_json()["id"]

    poi_image_response = admin_client.post(
        f"/api/points-of-interest/{create_response.get_json()['id']}/images",
        json={"image_id": image_id},
    )
    assert poi_image_response.status_code == 201
    assert poi_image_response.get_json() == {
        "point_id": create_response.get_json()["id"],
        "image_ids": [image_id],
    }

    poi_image_list_response = admin_client.get(
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


def test_api_route_endpoints(app: Flask, admin_client: FlaskClient, database: None) -> None:
    summary_polyline = '{"type":"LineString","coordinates":[[-122.48,37.83],[-122.45,37.85]]}'
    full_track = '{"type":"LineString","coordinates":[[-122.48,37.83,5],[-122.45,37.85,15]]}'

    with app.app_context():
        db = app.extensions["sqlalchemy"]
        creator = User(username="api-route", email="api-route@example.com", password_hash="x")
        db.session.add(creator)
        db.session.commit()
        creator_id = creator.id

    create_response = admin_client.post(
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

    list_response = admin_client.get(f"/api/routes?creator_id={creator_id}")
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


def test_api_segment_endpoints(app: Flask, admin_client: FlaskClient, database: None) -> None:
    summary_polyline = '{"type":"LineString","coordinates":[[-122.6,37.9],[-122.5,37.84]]}'
    full_track = '{"type":"LineString","coordinates":[[-122.6,37.9,50],[-122.5,37.84,12]]}'

    create_response = admin_client.post(
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

    list_response = admin_client.get("/api/segments")
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


def test_api_can_attach_segment_to_route(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
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

    attach_response = admin_client.post(
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


def test_api_activity_endpoints(app: Flask, admin_client: FlaskClient, database: None) -> None:
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

    create_response = admin_client.post(
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

    list_response = admin_client.get(f"/api/activities?athlete_id={athlete_id}&route_id={route_id}")
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


def test_api_image_endpoints(app: Flask, admin_client: FlaskClient, database: None) -> None:
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

    create_response = admin_client.post(
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

    list_response = admin_client.get(
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


def test_api_search_and_reindex_endpoints(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
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

    rebuild_response = admin_client.post("/api/search/reindex", json={})
    assert rebuild_response.status_code == 200
    assert rebuild_response.get_json()["indexed"] >= 2

    search_response = admin_client.get("/api/search?q=marin&type=group&type=event")
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

    limited_response = admin_client.get("/api/search?q=marin&limit=1")
    assert limited_response.status_code == 200
    limited_payload = limited_response.get_json()
    assert limited_payload is not None
    assert len(limited_payload["items"]) == 1

    missing_query_response = admin_client.get("/api/search")
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


def test_admin_search_page_renders_results(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
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

    response = admin_client.get("/admin/search?q=fairfax&type=group&type=route&limit=5")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Admin Search" in html
    assert "North Bay Climbers" in html
    assert "Bolinas Ridge Loop" in html
    assert "Fairfax, CA" in html


def test_admin_search_page_handles_empty_state(admin_client: FlaskClient, database: None) -> None:
    response = admin_client.get("/admin/search")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Start with a name, place, description fragment, or tag." in html


def test_admin_search_page_links_to_detail_views(
    app: Flask, admin_client: FlaskClient, database: None
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

    response = admin_client.get("/admin/search?q=summit")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert f"/admin/events/{event_id}" in html


def test_admin_group_detail_page_renders(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
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

    response = admin_client.get(f"/admin/groups/{group_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "East Bay Dirt" in html
    assert "Community gravel rides and route swaps" in html
    assert "Oakland, CA" in html


def test_admin_route_detail_page_renders(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        creator = User(username="route-curator", email="route-curator@example.com")
        creator.set_password("secret123")
        segment = Segment(
            name="Skyline Spur",
            type="connector",
            length=8.4,
            elevation_gain=420.0,
        )
        group = Group(
            name="Oakland Distance Club",
            shortname="oakland-distance-club",
            about_blurb="Long mixed-terrain routes from the hills",
            home_town="Oakland",
            home_state="CA",
        )
        route = Route(
            name="Skyline Traverse",
            desc="Long ridge route with mixed climbing",
            tags=["ridge", "climb"],
            city="Oakland",
            state="CA",
            length=54200.0,
            duration=182.0,
            elevation_gain=1430.0,
            grade=4.8,
            rating=4.6,
            private=False,
            athlete_id=77,
            src="strava",
            src_id="route-77",
            address="Joaquin Miller Park, Oakland, CA",
            start_latitude=37.81234,
            start_longitude=-122.18345,
            end_latitude=37.88123,
            end_longitude=-122.24456,
            elevation_array=[110.0, 340.0, 280.0],
            summary_polyline='{"type":"LineString","coordinates":[[-122.18345,37.81234],[-122.2,37.84],[-122.24456,37.88123]]}',
        )
        route.creator = creator
        route.groups.append(group)
        route.segments.append(segment)
        db.session.add_all([creator, group, segment, route])
        db.session.commit()
        link = GroupExternalUrl(
            route_id=route.id,
            url="https://example.com/skyline-traverse",
            type="source",
            name="Original route page",
            description="Full source record",
        )
        db.session.add(link)
        db.session.commit()
        route_id = route.id

    response = admin_client.get(f"/admin/routes/{route_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Skyline Traverse" in html
    assert "Long ridge route with mixed climbing" in html
    assert "1430.00" in html
    assert "Joaquin Miller Park, Oakland, CA" in html
    assert "37.81234, -122.18345" in html
    assert "54.2 km" in html
    assert "1430 m" in html
    assert "Elevation profile" in html
    assert "Explor View" in html
    assert "Route view" in html
    assert "Summary line" in html
    assert "Connected Records" in html
    assert "Oakland Distance Club" in html
    assert "Skyline Spur" in html
    assert "Original route page" in html


def test_admin_segment_detail_page_renders_full_record(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        route = Route(
            name="Redwood Access Loop",
            type="route",
            length=27500.0,
            elevation_gain=860.0,
        )
        segment = Segment(
            name="Redwood Wall",
            desc="A short steep ramp with a shaded approach",
            tags=["steep", "woods"],
            type="climb",
            subtype="paved",
            length=3200.0,
            duration=14.0,
            elevation_gain=355.0,
            elevation_loss=22.0,
            elev_high=902.0,
            elev_low=544.0,
            rating=4.9,
            grade=9.4,
            src="strava",
            src_id="segment-99",
            src_url="https://example.com/segments/redwood-wall",
            start_latitude=37.80123,
            start_longitude=-122.15432,
            end_latitude=37.81234,
            end_longitude=-122.14321,
            elevation_array=[544.0, 700.0, 902.0],
            summary_polyline='{"type":"LineString","coordinates":[[-122.15432,37.80123],[-122.14987,37.80654],[-122.14321,37.81234]]}',
            track_hash="abc123def456",
            track_maxspeed=38.4,
        )
        image = Image(
            title="Canopy switchback",
            caption="Tree cover through the steepest pitch",
            img_medium="https://images.example.com/redwood-wall.jpg",
            segment=segment,
        )
        segment.routes.append(route)
        db.session.add_all([route, segment, image])
        db.session.commit()
        segment_id = segment.id

    response = admin_client.get(f"/admin/segments/{segment_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Redwood Wall" in html
    assert "A short steep ramp with a shaded approach" in html
    assert "355.00" in html
    assert "Elevation loss" in html
    assert "Track hash" in html
    assert "abc123def456" in html
    assert "https://example.com/segments/redwood-wall" in html
    assert "37.80123, -122.15432" in html
    assert "Segment line" in html
    assert "Segment profile" in html
    assert "Redwood Access Loop" in html
    assert "Canopy switchback" in html


def test_admin_route_detail_page_skips_blank_stats_when_values_are_missing(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        route = Route(
            name="Sparse Ridge",
            type="route",
            length=18000.0,
            duration=64.0,
            elevation_gain=540.0,
            rating=None,
            grade=None,
        )
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    response = admin_client.get(f"/admin/routes/{route_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Rating" not in html
    assert "Grade" not in html
    assert "Distance" in html
    assert "Duration" in html
    assert "Elevation" in html


def test_to_storage_geometry_preserves_feature_collection_linework() -> None:
    from app.geometry import to_storage_geometry

    value = (
        '{"type":"FeatureCollection","features":['
        '{"type":"Feature","geometry":{"type":"LineString","coordinates":[[-122.1,37.1],[-122.2,37.2]]}},'
        '{"type":"Feature","geometry":{"type":"LineString","coordinates":[[-122.3,37.3],[-122.4,37.4]]}}'
        "]}"
    )

    stored = to_storage_geometry(value)

    assert stored is not None
    assert stored.startswith("MULTILINESTRING")
    assert "-122.1 37.1" in stored
    assert "-122.4 37.4" in stored


def test_leaflet_latlngs_keep_multiline_parts_separate() -> None:
    from app.routes import _leaflet_latlngs

    value = (
        '{"type":"MultiLineString","coordinates":['
        "[[-122.1,37.1],[-122.2,37.2]],"
        "[[-122.3,37.3],[-122.4,37.4]]"
        "]}"
    )

    latlngs = _leaflet_latlngs(value)

    assert latlngs == [
        [[37.1, -122.1], [37.2, -122.2]],
        [[37.3, -122.3], [37.4, -122.4]],
    ]


def test_browser_line_geometry_keeps_multiline_shape() -> None:
    from app.routes import _browser_line_geometry

    geometry = _browser_line_geometry(
        '{"type":"MultiLineString","coordinates":['
        "[[-122.1,37.1],[-122.2,37.2]],"
        "[[-122.3,37.3],[-122.4,37.4]]"
        "]}",
    )

    assert geometry is not None
    assert geometry["type"] == "MultiLineString"


def test_admin_event_detail_page_renders_full_record(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        ensure_canonical_lookup_rows()
        user = User(username="event-rider", email="event-rider@example.com")
        user.set_password("secret123")
        route = Route(name="Sunrise Loop", type="road", length=42000.0, elevation_gain=900.0)
        activity = Activity(name="Preview Spin", type="ride", length=24000.0)
        calendar = Calendar(name="Club Calendar", primary_activity="road", type="club")
        fee = EventFee(name="Entry", fee=25.0, description="Day-of ride support")
        image = Image(
            title="Start line",
            img_medium="https://images.example.com/start-line.jpg",
        )
        event = Event(
            name="Summit Rally",
            description="A full-day mountain meetup with staggered starts.",
            private=False,
            email="events@example.com",
            duration=240.0,
            primary_activity="cycling",
            type="road",
            subtype="climbing",
            url="https://example.com/events/summit-rally",
            reg_url="https://example.com/events/summit-rally/register",
            photo_url="https://images.example.com/summit-rally.jpg",
            logo="https://images.example.com/summit-logo.jpg",
            profile_photo="https://images.example.com/summit-profile.jpg",
            notes="Meet at the lower lot before rollout.",
            lat=37.88,
            lon=-122.25,
            town="Berkeley",
            state="CA",
            country="USA",
            route=route,
            activity=activity,
            tags=["climb", "community"],
        )
        event.calendars.append(calendar)
        event.fees.append(fee)
        event.images.append(image)
        event.invite(user)
        db.session.add_all([user, route, activity, calendar, fee, image, event])
        db.session.commit()
        event_id = event.id

    response = admin_client.get(f"/admin/events/{event_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Summit Rally" in html
    assert "A full-day mountain meetup with staggered starts." in html
    assert "https://example.com/events/summit-rally/register" in html
    assert "Club Calendar" in html
    assert "Entry" in html
    assert "Event footprint" in html
    assert "Event location" in html
    assert "Linked route" in html
    assert "Sunrise Loop" in html
    assert "Preview Spin" in html
    assert "event-rider" in html


def test_admin_calendar_detail_page_renders_map_first_record(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        group = Group(name="Calendar Club", shortname="calendar-club", home_town="Oakland")
        route = Route(
            name="Calendar Route",
            type="road",
            summary_polyline='{"type":"LineString","coordinates":[[-122.27,37.8],[-122.25,37.82],[-122.22,37.84]]}',
        )
        event = Event(
            name="Calendar Rally",
            type="event",
            lat=37.81,
            lon=-122.26,
            town="Oakland",
            state="CA",
            route=route,
        )
        calendar = Calendar(
            name="Spring Calendar",
            description="A rolling set of East Bay events.",
            primary_activity="cycling",
            type="club",
            group=group,
        )
        calendar.events.append(event)
        db.session.add_all([group, route, event, calendar])
        db.session.commit()
        calendar_id = calendar.id

    response = admin_client.get(f"/admin/calendars/{calendar_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Spring Calendar" in html
    assert "Calendar footprint" in html
    assert "Event markers" in html
    assert "Route network" in html
    assert "Calendar Rally" in html


def test_admin_point_of_interest_detail_page_renders_full_record(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        point = PointOfInterest(
            name="Ridgeline Water Stop",
            description="Reliable refill spot tucked behind the visitor center.",
            type="water",
            subtype="fountain",
            lat=37.8123,
            lon=-122.1812,
            url="https://example.com/poi/ridgeline-water-stop",
            icon="drop",
            tags=["water", "support"],
        )
        image = Image(
            title="Bottle fill station",
            img_medium="https://images.example.com/water-stop.jpg",
        )
        point.images.append(image)
        db.session.add_all([point, image])
        db.session.commit()
        point_id = point.id

    response = admin_client.get(f"/admin/points-of-interest/{point_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Ridgeline Water Stop" in html
    assert "Reliable refill spot tucked behind the visitor center." in html
    assert "37.81230, -122.18120" in html
    assert "https://example.com/poi/ridgeline-water-stop" in html
    assert "Bottle fill station" in html


def test_admin_activity_detail_page_renders_full_record(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        route = Route(
            name="Headlands Long Loop",
            type="mixed",
            length=61000.0,
            elevation_gain=1800.0,
        )
        activity = Activity(
            name="Sunday Headlands Ride",
            desc="Fast rollout, foggy climbs, and a calm return along the water.",
            private=False,
            photo_url="https://images.example.com/headlands-ride.jpg",
            tags=["endurance", "coastal"],
            duration=205.0,
            length=63400.0,
            elevation_gain=1910.0,
            average_speed=18.6,
            max_speed=42.3,
            moving_time=188.0,
            total_elevation_gain=1955.0,
            elev_high=1180.0,
            elev_low=12.0,
            type="ride",
            subtype="road",
            src="strava",
            src_id="activity-42",
            start_latitude=37.8061,
            start_longitude=-122.4775,
            end_latitude=37.8072,
            end_longitude=-122.4754,
            summary_polyline='{"type":"LineString","coordinates":[[-122.4775,37.8061],[-122.4763,37.8068],[-122.4754,37.8072]]}',
            route=route,
        )
        image = Image(
            title="Fog bank over the bridge",
            img_medium="https://images.example.com/headlands-fog.jpg",
            activity=activity,
        )
        db.session.add_all([route, activity, image])
        db.session.commit()
        activity_id = activity.id

    response = admin_client.get(f"/admin/activities/{activity_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Sunday Headlands Ride" in html
    assert "Fast rollout, foggy climbs, and a calm return along the water." in html
    assert "1910.00" in html
    assert "activity-42" in html
    assert "37.80610, -122.47750" in html
    assert "Explor View" in html
    assert "Activity trace" in html
    assert "Climbing shape" in html
    assert "Headlands Long Loop" in html
    assert "Fog bank over the bridge" in html


def test_admin_group_edit_page_updates_group_and_search(
    app: Flask, admin_client: FlaskClient, database: None
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

    response = admin_client.post(
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
    app: Flask, admin_client: FlaskClient, database: None
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

    response = admin_client.post(
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
    app: Flask, admin_client: FlaskClient, database: None
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

    response = admin_client.post(
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
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        group = Group(name="Marin Dawn Patrol", shortname="marin-dawn-patrol")
        route = Route(name="Pine Mountain Figure Eight")
        event = Event(name="Breakfast Rollout")
        db.session.add_all([group, route, event])
        db.session.commit()

    response = admin_client.get("/admin")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Control room for the rebuilt domain." in html
    assert "Marin Dawn Patrol" in html
    assert "Pine Mountain Figure Eight" in html
    assert "Breakfast Rollout" in html
    assert "/admin/groups/new" in html
    assert "/admin/routes/new" in html
    assert "/admin/events/new" in html
    assert "/admin/users/new" in html
    assert "Dashboard" in html
    assert "Search" in html


def test_admin_collection_pages_render(admin_client: FlaskClient, database: None) -> None:
    for path in ("/admin/images", "/admin/links", "/admin/dues", "/admin/fees"):
        response = admin_client.get(path)
        assert response.status_code == 200
        assert "Back to dashboard" in response.get_data(as_text=True)


def test_admin_group_create_page_creates_group_and_search_document(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    response = admin_client.post(
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
    assert "Group created." in html

    with app.app_context():
        hits = search_documents(query="golden gate rollers", types=["group"])
        assert len(hits) == 1


def test_admin_route_create_page_creates_route_and_search_document(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    response = admin_client.post(
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
    assert "Route created." in html

    with app.app_context():
        hits = search_documents(query="wildcat figure eight", types=["route"])
        assert len(hits) == 1


def test_admin_event_create_page_creates_event_and_search_document(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    response = admin_client.post(
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
    assert "Event created." in html

    with app.app_context():
        hits = search_documents(query="sunday harbor meetup", types=["event"])
        assert len(hits) == 1


def test_admin_event_create_invalid_related_id_shows_flash_error(
    admin_client: FlaskClient, database: None
) -> None:
    response = admin_client.post(
        "/admin/events/new",
        data={
            "name": "Broken Link Event",
            "route_id": "9999",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Route id was not found." in html
    assert "Broken Link Event" not in html


def test_admin_detail_pages_show_recent_activity_links(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        current_group = Group(name="Current Group", shortname="current-group")
        recent_group = Group(name="Recent Group", shortname="recent-group")
        recent_route = Route(name="Recent Route")
        db.session.add_all([current_group, recent_group, recent_route])
        db.session.commit()
        current_group_id = current_group.id

    response = admin_client.get(f"/admin/groups/{current_group_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Recent Activity" in html
    assert "Recent Group" in html
    assert "Recent Route" in html


def test_admin_dashboard_includes_remaining_create_links(
    admin_client: FlaskClient, database: None
) -> None:
    response = admin_client.get("/admin")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "/admin/segments/new" in html
    assert "/admin/points-of-interest/new" in html
    assert "/admin/activities/new" in html
    assert "/admin/images/new" in html
    assert "/admin/links/new" in html
    assert "/admin/dues/new" in html
    assert "/admin/fees/new" in html


def test_admin_segment_create_and_edit_flow_updates_search(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    create_response = admin_client.post(
        "/admin/segments/new",
        data={
            "name": "Summit Spur",
            "desc": "Steep gravel connector",
            "type": "gravel",
            "tags": "gravel, climb",
        },
        follow_redirects=True,
    )
    assert create_response.status_code == 200
    create_html = create_response.get_data(as_text=True)
    assert "Segment created." in create_html
    assert "Summit Spur" in create_html

    with app.app_context():
        segment_hit = search_documents(query="summit spur", types=["segment"])
        assert len(segment_hit) == 1
        segment_id = segment_hit[0].entity_id

    edit_response = admin_client.post(
        f"/admin/segments/{segment_id}/edit",
        data={
            "name": "Summit Spur Revised",
            "desc": "Steep gravel connector with views",
            "type": "gravel",
            "tags": "gravel, views",
        },
        follow_redirects=True,
    )
    assert edit_response.status_code == 200
    edit_html = edit_response.get_data(as_text=True)
    assert "Segment saved." in edit_html
    assert "Summit Spur Revised" in edit_html

    with app.app_context():
        search_hits = search_documents(query="summit spur revised", types=["segment"])
        assert [result.entity_id for result in search_hits] == [segment_id]


def test_admin_point_of_interest_create_and_edit_flow_updates_search(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    create_response = admin_client.post(
        "/admin/points-of-interest/new",
        data={
            "name": "Vista Point",
            "description": "Bay overlook",
            "type": "viewpoint",
            "tags": "view, sunset",
        },
        follow_redirects=True,
    )
    assert create_response.status_code == 200
    create_html = create_response.get_data(as_text=True)
    assert "Point of interest created." in create_html
    assert "Vista Point" in create_html

    with app.app_context():
        point_hit = search_documents(query="vista point", types=["point_of_interest"])
        assert len(point_hit) == 1
        point_id = point_hit[0].entity_id

    edit_response = admin_client.post(
        f"/admin/points-of-interest/{point_id}/edit",
        data={
            "name": "Vista Point North",
            "description": "Bay overlook with wind shelter",
            "type": "viewpoint",
            "tags": "view, shelter",
        },
        follow_redirects=True,
    )
    assert edit_response.status_code == 200
    edit_html = edit_response.get_data(as_text=True)
    assert "Point of interest saved." in edit_html
    assert "Vista Point North" in edit_html

    with app.app_context():
        search_hits = search_documents(query="vista point north", types=["point_of_interest"])
        assert [result.entity_id for result in search_hits] == [point_id]


def test_admin_activity_create_and_edit_flow_updates_search(
    app: Flask, admin_client: FlaskClient, database: None
) -> None:
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        route = Route(name="Activity Anchor Route")
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    create_response = admin_client.post(
        "/admin/activities/new",
        data={
            "name": "Morning Tempo",
            "desc": "Fast effort before work",
            "route_id": str(route_id),
            "type": "ride",
            "tags": "tempo, morning",
        },
        follow_redirects=True,
    )
    assert create_response.status_code == 200
    create_html = create_response.get_data(as_text=True)
    assert "Activity created." in create_html
    assert "Morning Tempo" in create_html

    with app.app_context():
        activity_hit = search_documents(query="morning tempo", types=["activity"])
        assert len(activity_hit) == 1
        activity_id = activity_hit[0].entity_id

    edit_response = admin_client.post(
        f"/admin/activities/{activity_id}/edit",
        data={
            "name": "Morning Tempo Plus",
            "desc": "Fast effort before work with extra climbing",
            "route_id": str(route_id),
            "type": "ride",
            "tags": "tempo, climbing",
        },
        follow_redirects=True,
    )
    assert edit_response.status_code == 200
    edit_html = edit_response.get_data(as_text=True)
    assert "Activity saved." in edit_html
    assert "Morning Tempo Plus" in edit_html

    with app.app_context():
        search_hits = search_documents(query="morning tempo plus", types=["activity"])
        assert [result.entity_id for result in search_hits] == [activity_id]
