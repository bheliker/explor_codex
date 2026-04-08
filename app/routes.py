from __future__ import annotations

import json
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any, Callable, Sequence, TypeVar, cast

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, logout_user  # type: ignore[import-untyped]
from sqlalchemy import String, func, or_, select
from sqlalchemy import cast as sql_cast
from sqlalchemy.orm import load_only, selectinload

from app.bootstrap import ensure_canonical_lookup_rows
from app.extensions import db, login_manager
from app.geometry import point_coordinates
from app.models import (
    Activity,
    Calendar,
    Event,
    EventFee,
    EventInvitation,
    Group,
    GroupDues,
    GroupExternalUrl,
    Image,
    Membership,
    PointOfInterest,
    Route,
    SearchDocument,
    Segment,
    User,
    group_routes,
    route_segments,
)
from app.services import (
    SEARCHABLE_ENTITY_TYPES,
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
    create_user,
    ensure_group_membership,
    list_activities,
    list_images,
    list_points_of_interest,
    list_routes,
    list_segments,
    list_users,
    parse_search_types,
    rebuild_search_documents,
    search_documents,
    set_rsvp,
    update_activity,
    update_event,
    update_event_fee,
    update_group,
    update_group_dues,
    update_group_link,
    update_image,
    update_point_of_interest,
    update_route,
    update_segment,
    update_user,
)

bp = Blueprint("core", __name__)
ModelT = TypeVar("ModelT")

COLOR_TOKENS: tuple[tuple[str, str], ...] = (
    ("--bg", "#dfe7f1"),
    ("--bg-deep", "#cfd9e7"),
    ("--surface", "rgba(242, 247, 252, 0.86)"),
    ("--surface-strong", "#f5f9fd"),
    ("--surface-dark", "#2b3745"),
    ("--ink", "#17212c"),
    ("--heading", "#203247"),
    ("--muted", "#58677a"),
    ("--muted-soft", "#708198"),
    ("--line", "rgba(32, 50, 71, 0.12)"),
    ("--line-strong", "rgba(32, 50, 71, 0.24)"),
    ("--accent", "#2c668f"),
    ("--accent-strong", "#234c6b"),
    ("--accent-soft", "rgba(44, 102, 143, 0.12)"),
    ("--warm-accent", "#ff8900"),
    ("--warm-accent-soft", "rgba(255, 137, 0, 0.12)"),
    ("--signal", "#ebde79"),
)

NON_COLOR_TOKENS: tuple[tuple[str, str], ...] = (
    ("--shadow-lg", "0 28px 60px rgba(33, 30, 26, 0.12)"),
    ("--shadow-md", "0 18px 34px rgba(33, 30, 26, 0.08)"),
    ("--radius-xl", "30px"),
    ("--radius-lg", "24px"),
    ("--radius-md", "18px"),
)

PUBLIC_BROWSER_LIMIT = 30


class AdminFormError(ValueError):
    pass


@bp.get("/")
def index() -> tuple[dict[str, str], int]:
    return {"message": "explor_codex is ready"}, 200


@bp.get("/landing")
def landing() -> str:
    return render_template(
        "public/landing.html",
        feature_cards=[
            {
                "eyebrow": "1 / Discover",
                "body": (
                    "Search routes, groups, events, and places from one rebuilt domain "
                    "instead of stitching tools together by hand."
                ),
                "title": "Find the next ride faster.",
            },
            {
                "eyebrow": "2 / Coordinate",
                "body": (
                    "Browser-backed admin and account flows make it easier to update "
                    "records, manage people, and keep context close to the data."
                ),
                "title": "Keep coordination inside the platform.",
            },
            {
                "eyebrow": "3 / Grow",
                "body": (
                    "The new Flask app keeps the backend modern while making room to port "
                    "the strongest product ideas from the original design language."
                ),
                "title": "Rebuild without losing the original ambition.",
            },
        ],
        stats=[
            {"label": "groups", "count": _count_records(Group)},
            {"label": "routes", "count": _count_records(Route)},
            {"label": "events", "count": _count_records(Event)},
            {"label": "search docs", "count": _count_records(SearchDocument)},
        ],
    )


@bp.get("/discover")
def discover() -> str:
    query = request.args.get("q", default="", type=str).strip()
    parsed_types = parse_search_types(request.args.getlist("type"))
    requested_limit = request.args.get("limit", default=12, type=int)
    limit = min(max(requested_limit, 1), 24)

    if query:
        documents = search_documents(query=query, types=parsed_types or None, limit=limit)
    else:
        statement = select(SearchDocument).order_by(SearchDocument.updated_at.desc()).limit(limit)
        documents = list(db.session.scalars(statement))

    return render_template(
        "public/discover.html",
        entity_types=SEARCHABLE_ENTITY_TYPES,
        limit=limit,
        query=query,
        results=[_public_search_result_item(document) for document in documents],
        selected_types=parsed_types,
        total_documents=_count_records(SearchDocument),
    )


@bp.get("/routes")
def public_routes_route() -> str:
    bundle = _route_browser_bundle()
    return render_template(
        "public/entity_browser.html",
        collection_key="routes",
        collection_label="Routes",
        collection_description=(
            "Browse saved rides the way the product wants to be used: map-first, "
            "distance-aware, and ready to sort by the effort that matters today."
        ),
        empty_copy="No routes are available yet.",
        hero_eyebrow="Route Browser",
        hero_title="Browse routes with the map and list moving together.",
        hero_body=(
            "This is the first rebuild pass on the most important navigation surface. "
            "Search, sort, grid or list view, and map-area filtering now live on one page."
        ),
        page_data=_browser_page_payload(
            collection_key="routes",
            collection_label="Routes",
            api_url=url_for("core.public_route_browser_api_route"),
            bundle=bundle,
            filter_options=_route_browser_filter_options(),
        ),
        server_items=cast(list[dict[str, object]], bundle["items"])[:18],
        summary_stats=_browser_summary_stats(
            cast(list[dict[str, object]], bundle["items"]),
            secondary_label="clubs linked",
        ),
        total_available=_count_records(Route),
        visible_limit=cast(int, bundle["limit"]),
    )


@bp.get("/segments")
def public_segments_route() -> str:
    bundle = _segment_browser_bundle()
    return render_template(
        "public/entity_browser.html",
        collection_key="segments",
        collection_label="Segments",
        collection_description=(
            "Scan the decisive climbs, connectors, and crux efforts that shape bigger "
            "days out, then sort them by proximity, elevation, or duration."
        ),
        empty_copy="No segments are available yet.",
        hero_eyebrow="Segment Browser",
        hero_title="Browse segments like the defining efforts they are.",
        hero_body=(
            "The segment home page uses the same left-pane browse rhythm and synced map "
            "view so short efforts stay discoverable inside the same system."
        ),
        page_data=_browser_page_payload(
            collection_key="segments",
            collection_label="Segments",
            api_url=url_for("core.public_segment_browser_api_route"),
            bundle=bundle,
            filter_options=_segment_browser_filter_options(),
        ),
        server_items=cast(list[dict[str, object]], bundle["items"])[:18],
        summary_stats=_browser_summary_stats(
            cast(list[dict[str, object]], bundle["items"]),
            secondary_label="routes linked",
        ),
        total_available=_count_records(Segment),
        visible_limit=cast(int, bundle["limit"]),
    )


@bp.get("/api/browser/routes")
def public_route_browser_api_route() -> tuple[dict[str, object], int]:
    return _route_browser_bundle(), HTTPStatus.OK


@bp.get("/api/browser/segments")
def public_segment_browser_api_route() -> tuple[dict[str, object], int]:
    return _segment_browser_bundle(), HTTPStatus.OK


@bp.get("/api/browser/areas")
def public_browser_area_search_route() -> tuple[dict[str, object], int]:
    query = request.args.get("q", default="", type=str).strip()
    return {"items": _browser_area_search_results(query)}, HTTPStatus.OK


@bp.get("/palette")
def palette() -> str:
    return render_template(
        "public/palette.html",
        color_tokens=[
            {
                "label": label,
                "style": f"background: {value};",
                "value": value,
            }
            for label, value in COLOR_TOKENS
        ],
        non_color_tokens=[
            {
                "label": label,
                "value": value,
            }
            for label, value in NON_COLOR_TOKENS
        ],
    )


@bp.get("/health")
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


@bp.before_app_request
def protect_admin_routes() -> Any | None:
    if request.path.startswith("/api/") and request.method != "GET":
        if not current_user.is_authenticated:
            return {"error": "authentication required"}, HTTPStatus.UNAUTHORIZED
        if not getattr(current_user, "active", False):
            logout_user()
            return {"error": "account is inactive"}, HTTPStatus.FORBIDDEN
        if not getattr(current_user, "site_admin", False):
            return {"error": "site admin access required"}, HTTPStatus.FORBIDDEN
        return None

    if request.endpoint is None or not request.endpoint.startswith("core.admin_"):
        return None
    if not current_user.is_authenticated:
        return login_manager.unauthorized()
    if not getattr(current_user, "active", False):
        logout_user()
        flash("Your account is inactive.", "error")
        return redirect(url_for("auth.login"))
    if not getattr(current_user, "site_admin", False):
        abort(HTTPStatus.FORBIDDEN)
    return None


@bp.get("/admin/search")
def admin_search_route() -> str:
    query = request.args.get("q", default="", type=str).strip()
    parsed_types = parse_search_types(request.args.getlist("type"))
    requested_limit = request.args.get("limit", default=25, type=int)
    limit = min(max(requested_limit, 1), 100)

    results = (
        search_documents(query=query, types=parsed_types or None, limit=limit) if query else []
    )
    total_documents = db.session.scalar(select(func.count()).select_from(SearchDocument)) or 0

    return render_template(
        "admin/search.html",
        entity_types=SEARCHABLE_ENTITY_TYPES,
        limit=limit,
        query=query,
        results=[_admin_search_result_item(result) for result in results],
        selected_types=parsed_types,
        total_documents=total_documents,
    )


@bp.get("/admin")
def admin_dashboard_route() -> str:
    return render_template(
        "admin/dashboard.html",
        sections=[
            {
                "items": [_dashboard_user_item(user) for user in _recent_records(User)],
                "new_url": url_for("core.admin_user_new_route"),
                "title": "Recent Users",
            },
            {
                "items": [_dashboard_group_item(group) for group in _recent_records(Group)],
                "new_url": url_for("core.admin_group_new_route"),
                "title": "Recent Groups",
            },
            {
                "items": [_dashboard_route_item(route) for route in _recent_records(Route)],
                "new_url": url_for("core.admin_route_new_route"),
                "title": "Recent Routes",
            },
            {
                "items": [
                    _dashboard_calendar_item(calendar) for calendar in _recent_records(Calendar)
                ],
                "new_url": None,
                "title": "Recent Calendars",
            },
            {
                "items": [_dashboard_segment_item(segment) for segment in _recent_records(Segment)],
                "new_url": url_for("core.admin_segment_new_route"),
                "title": "Recent Segments",
            },
            {
                "items": [_dashboard_event_item(event) for event in _recent_records(Event)],
                "new_url": url_for("core.admin_event_new_route"),
                "title": "Recent Events",
            },
            {
                "items": [_dashboard_poi_item(point) for point in _recent_records(PointOfInterest)],
                "new_url": url_for("core.admin_point_of_interest_new_route"),
                "title": "Recent Points Of Interest",
            },
            {
                "items": [
                    _dashboard_activity_item(activity) for activity in _recent_records(Activity)
                ],
                "new_url": url_for("core.admin_activity_new_route"),
                "title": "Recent Activities",
            },
        ],
        stats=[
            {"count": _count_records(User), "label": "users"},
            {"count": _count_records(Group), "label": "groups"},
            {"count": _count_records(Route), "label": "routes"},
            {"count": _count_records(Calendar), "label": "calendars"},
            {"count": _count_records(Segment), "label": "segments"},
            {"count": _count_records(Event), "label": "events"},
            {"count": _count_records(PointOfInterest), "label": "pois"},
            {"count": _count_records(Activity), "label": "activities"},
            {"count": _count_records(SearchDocument), "label": "search docs"},
        ],
    )


@bp.get("/admin/users")
def admin_user_list_route() -> str:
    users = list_users()
    return render_template(
        "admin/users.html",
        page_title="Users",
        users=[_dashboard_user_item(user) for user in users],
    )


@bp.get("/admin/users/<int:user_id>")
def admin_user_detail_route(user_id: int) -> str:
    user = _get_or_404(User, user_id)
    return render_template(
        "admin/detail.html",
        detail_rows=_detail_rows(
            [
                ("Username", user.username),
                ("Email", user.email),
                ("First name", user.firstname),
                ("Last name", user.lastname),
                ("Account type", user.account_type),
                ("Units", user.units),
                ("Active", "yes" if user.active else "no"),
                ("Site admin", "yes" if user.site_admin else "no"),
                ("Home town", user.home_town),
                ("Home state", user.home_state),
                ("Home country", user.home_country),
                ("Home gym", user.home_gym),
                ("Last login", user.last_login_at),
            ]
        ),
        entity_id=user.id,
        entity_type_label="User",
        edit_url=url_for("core.admin_user_edit_route", user_id=user.id),
        location=_join_location(user.home_town, user.home_state, user.home_country),
        media_previews=None,
        page_title=user.display_name,
        recent_links=_recent_user_links(exclude_user_id=user.id),
        subtitle=user.email,
        tags=_combine_tags(user.tags, user.preference_tags),
    )


@bp.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
def admin_user_edit_route(user_id: int) -> str | Any:
    user = _get_or_404(User, user_id)
    if request.method == "POST":
        password = _form_optional_str("password")
        password_confirm = _form_optional_str("password_confirm")
        if password and password != password_confirm:
            flash("Password confirmation did not match.", "error")
        elif password and len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            try:
                update_user(
                    user,
                    username=_form_required_str("username"),
                    email=_form_required_str("email"),
                    password=password,
                    firstname=_form_optional_str("firstname"),
                    lastname=_form_optional_str("lastname"),
                    account_type=_form_optional_str("account_type"),
                    units=_form_optional_str("units") or "metric",
                    preference_tags=_form_csv_list("preference_tags"),
                    tags=_form_csv_list("tags"),
                    home_town=_form_optional_str("home_town"),
                    home_state=_form_optional_str("home_state"),
                    home_country=_form_optional_str("home_country"),
                    home_gym=_form_optional_str("home_gym"),
                    home_latlng=_form_optional_str("home_latlng"),
                    geoll=_form_optional_str("geoll"),
                    active=_form_bool("active"),
                    site_admin=_form_bool("site_admin"),
                )
            except ValueError as exc:
                flash(str(exc), "error")
            else:
                flash("User saved.", "success")
                return redirect(url_for("core.admin_user_detail_route", user_id=user.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=url_for("core.admin_user_detail_route", user_id=user.id),
        entity_id=user.id,
        entity_type_label="User",
        fields=[
            _edit_text_field("username", "Username", user.username),
            _edit_text_field("email", "Email", user.email),
            _edit_text_field("firstname", "First name", user.firstname),
            _edit_text_field("lastname", "Last name", user.lastname),
            _edit_text_field("account_type", "Account type", user.account_type),
            _edit_text_field("units", "Units (metric or imperial)", user.units),
            _edit_checkbox_field("active", "Active", user.active),
            _edit_checkbox_field("site_admin", "Site admin", user.site_admin),
            _edit_text_field("home_town", "Home town", user.home_town),
            _edit_text_field("home_state", "Home state", user.home_state),
            _edit_text_field("home_country", "Home country", user.home_country),
            _edit_text_field("home_gym", "Home gym", user.home_gym),
            _edit_text_field("home_latlng", "Home latlng", user.home_latlng),
            _edit_text_field("geoll", "Geometry", user.geoll),
            _edit_text_field("tags", "Tags (comma separated)", _csv_value(user.tags)),
            _edit_text_field(
                "preference_tags",
                "Preference tags (comma separated)",
                _csv_value(user.preference_tags),
            ),
            _edit_text_field("password", "New password", None, kind="password"),
            _edit_text_field(
                "password_confirm",
                "Confirm new password",
                None,
                kind="password",
            ),
        ],
        intro_text="Manage account details, activation state, and site-admin access.",
        mode_title="Edit",
        page_title=user.display_name,
        submit_label="Save Changes",
    )


@bp.route("/admin/users/new", methods=["GET", "POST"])
def admin_user_new_route() -> str | Any:
    if request.method == "POST":
        password = _form_required_str("password")
        password_confirm = _form_required_str("password_confirm")
        if password != password_confirm:
            flash("Password confirmation did not match.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            try:
                user = create_user(
                    username=_form_required_str("username"),
                    email=_form_required_str("email"),
                    password=password,
                    firstname=_form_optional_str("firstname"),
                    lastname=_form_optional_str("lastname"),
                    account_type=_form_optional_str("account_type"),
                    units=_form_optional_str("units") or "metric",
                    preference_tags=_form_csv_list("preference_tags"),
                    tags=_form_csv_list("tags"),
                    home_town=_form_optional_str("home_town"),
                    home_state=_form_optional_str("home_state"),
                    home_country=_form_optional_str("home_country"),
                    home_gym=_form_optional_str("home_gym"),
                    home_latlng=_form_optional_str("home_latlng"),
                    geoll=_form_optional_str("geoll"),
                    active=_form_bool("active"),
                    site_admin=_form_bool("site_admin"),
                )
            except ValueError as exc:
                flash(str(exc), "error")
            else:
                flash("User created.", "success")
                return redirect(url_for("core.admin_user_detail_route", user_id=user.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=None,
        entity_id=None,
        entity_type_label="User",
        fields=[
            _edit_text_field("username", "Username", None),
            _edit_text_field("email", "Email", None),
            _edit_text_field("firstname", "First name", None),
            _edit_text_field("lastname", "Last name", None),
            _edit_text_field("account_type", "Account type", None),
            _edit_text_field("units", "Units (metric or imperial)", "metric"),
            _edit_checkbox_field("active", "Active", True),
            _edit_checkbox_field("site_admin", "Site admin", False),
            _edit_text_field("home_town", "Home town", None),
            _edit_text_field("home_state", "Home state", None),
            _edit_text_field("home_country", "Home country", None),
            _edit_text_field("home_gym", "Home gym", None),
            _edit_text_field("home_latlng", "Home latlng", None),
            _edit_text_field("geoll", "Geometry", None),
            _edit_text_field("tags", "Tags (comma separated)", None),
            _edit_text_field("preference_tags", "Preference tags (comma separated)", None),
            _edit_text_field("password", "Password", None, kind="password"),
            _edit_text_field("password_confirm", "Confirm password", None, kind="password"),
        ],
        intro_text="Create a user account directly from the admin UI.",
        mode_title="Create",
        page_title="User",
        submit_label="Create User",
    )


@bp.get("/admin/calendars")
def admin_calendar_list_route() -> str:
    calendars = list(db.session.scalars(select(Calendar).order_by(Calendar.id)))
    return render_template(
        "admin/collection.html",
        page_title="Calendars",
        intro_text="Browse calendar records as spatial programs and event containers.",
        new_url=None,
        records=[_dashboard_calendar_item(calendar) for calendar in calendars],
    )


@bp.get("/admin/calendars/<int:calendar_id>")
def admin_calendar_detail_route(calendar_id: int) -> str:
    calendar = _get_or_404(Calendar, calendar_id)
    return render_template(
        "admin/detail.html",
        detail_rows=_detail_rows(
            [
                ("Description", calendar.description),
                ("Primary activity", calendar.primary_activity),
                ("Type", calendar.type),
                ("Subtype", calendar.subtype),
                ("Private", calendar.private),
                ("Owner ID", calendar.owner_id),
                ("Group ID", calendar.group_id, _admin_detail_url("group", calendar.group_id)),
                ("URL", calendar.url, calendar.url),
                ("Notes", calendar.notes),
                ("Created", calendar.date_created),
                ("Updated", calendar.date_updated),
                ("Events", len(calendar.events)),
            ]
        ),
        entity_id=calendar.id,
        entity_type_label="Calendar",
        edit_url=None,
        location=calendar.group.name if calendar.group is not None else None,
        media_previews=_media_previews(
            [
                ("Photo", calendar.photo_url),
                ("Logo", calendar.logo),
                ("Profile photo", calendar.profile_photo),
            ]
        ),
        page_title=calendar.name or "Calendar",
        recent_links=_recent_activity_links(exclude=("calendar", calendar.id)),
        related_sections=_calendar_related_sections(calendar),
        story_sections=_calendar_story_sections(calendar),
        subtitle=calendar.subtype or calendar.type or calendar.primary_activity,
        tags=calendar.tags,
        visual_sections=_calendar_visual_sections(calendar),
        stats_bar=_calendar_stats_bar(calendar),
    )


@bp.get("/admin/images")
def admin_image_list_route() -> str:
    images = list_images()
    return render_template(
        "admin/collection.html",
        page_title="Images",
        intro_text="Manage uploaded image metadata and ownership links.",
        new_url=url_for("core.admin_image_new_route"),
        records=[_dashboard_image_item(image) for image in images],
    )


@bp.get("/admin/images/<int:image_id>")
def admin_image_detail_route(image_id: int) -> str:
    image = _get_or_404(Image, image_id)
    return render_template(
        "admin/detail.html",
        detail_rows=_detail_rows(
            [
                (
                    "Photographer ID",
                    image.photographer_id,
                    _admin_detail_url("user", image.photographer_id),
                ),
                ("Group ID", image.group_id, _admin_detail_url("group", image.group_id)),
                ("Segment ID", image.segment_id, _admin_detail_url("segment", image.segment_id)),
                (
                    "Activity ID",
                    image.activity_id,
                    _admin_detail_url("activity", image.activity_id),
                ),
                ("Caption", image.caption),
                ("Alt text", image.alt_txt),
                ("Latitude/Longitude", image.latlng),
                ("URL", image.url),
            ]
        ),
        entity_id=image.id,
        entity_type_label="Image",
        edit_url=url_for("core.admin_image_edit_route", image_id=image.id),
        location=None,
        media_previews=_media_previews(
            [
                ("Thumb", image.img_thumb),
                ("Small", image.img_small),
                ("Medium", image.img_medium),
                ("Large", image.img_large),
                ("Canonical", image.url),
            ]
        ),
        page_title=image.title or "Image",
        recent_links=_recent_image_links(exclude_image_id=image.id),
        subtitle=image.img_medium or image.url,
        tags=image.tags,
    )


@bp.route("/admin/images/<int:image_id>/edit", methods=["GET", "POST"])
def admin_image_edit_route(image_id: int) -> str | Any:
    image = _get_or_404(Image, image_id)
    if request.method == "POST":
        try:
            update_image(
                image,
                photographer=_optional_related_record(User, "photographer_id"),
                group=_optional_related_record(Group, "group_id"),
                segment=_optional_related_record(Segment, "segment_id"),
                activity=_optional_related_record(Activity, "activity_id"),
                img_small=_form_optional_str("img_small"),
                img_medium=_form_optional_str("img_medium"),
                img_large=_form_optional_str("img_large"),
                img_thumb=_form_optional_str("img_thumb"),
                alt_txt=_form_optional_str("alt_txt"),
                title=_form_optional_str("title"),
                caption=_form_optional_str("caption"),
                latlng=_form_optional_str("latlng"),
                geoll=_form_optional_str("geoll"),
                tags=_form_csv_list("tags"),
                url=_form_optional_str("url"),
            )
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Image saved.", "success")
            return redirect(url_for("core.admin_image_detail_route", image_id=image.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=url_for("core.admin_image_detail_route", image_id=image.id),
        entity_id=image.id,
        entity_type_label="Image",
        fields=_image_fields(image),
        intro_text="Adjust image ownership and media metadata from the admin UI.",
        mode_title="Edit",
        page_title=image.title or "Image",
        submit_label="Save Changes",
    )


@bp.route("/admin/images/new", methods=["GET", "POST"])
def admin_image_new_route() -> str | Any:
    if request.method == "POST":
        try:
            image = create_image(
                photographer=_optional_related_record(User, "photographer_id"),
                group=_optional_related_record(Group, "group_id"),
                segment=_optional_related_record(Segment, "segment_id"),
                activity=_optional_related_record(Activity, "activity_id"),
                img_small=_form_optional_str("img_small"),
                img_medium=_form_optional_str("img_medium"),
                img_large=_form_optional_str("img_large"),
                img_thumb=_form_optional_str("img_thumb"),
                alt_txt=_form_optional_str("alt_txt"),
                title=_form_optional_str("title"),
                caption=_form_optional_str("caption"),
                latlng=_form_optional_str("latlng"),
                geoll=_form_optional_str("geoll"),
                tags=_form_csv_list("tags"),
                url=_form_optional_str("url"),
            )
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Image created.", "success")
            return redirect(url_for("core.admin_image_detail_route", image_id=image.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=None,
        entity_id=None,
        entity_type_label="Image",
        fields=_image_fields(None),
        intro_text="Create an image record and assign it to the right owner records.",
        mode_title="Create",
        page_title="Image",
        submit_label="Create Image",
    )


@bp.get("/admin/links")
def admin_link_list_route() -> str:
    links = list(db.session.scalars(select(GroupExternalUrl).order_by(GroupExternalUrl.id)))
    return render_template(
        "admin/collection.html",
        page_title="Links",
        intro_text="Manage shared external links for groups and routes.",
        new_url=url_for("core.admin_link_new_route"),
        records=[_dashboard_link_item(link) for link in links],
    )


@bp.get("/admin/links/<int:link_id>")
def admin_link_detail_route(link_id: int) -> str:
    link = _get_or_404(GroupExternalUrl, link_id)
    return render_template(
        "admin/detail.html",
        detail_rows=_detail_rows(
            [
                ("Group ID", link.group_id, _admin_detail_url("group", link.group_id)),
                ("Route ID", link.route_id, _admin_detail_url("route", link.route_id)),
                ("Type", link.type),
                ("Subtype", link.subtype),
                ("URL", link.url),
                ("Description", link.description),
                ("Icon", link.icon),
                ("Image", link.img),
            ]
        ),
        entity_id=link.id,
        entity_type_label="Link",
        edit_url=url_for("core.admin_link_edit_route", link_id=link.id),
        location=None,
        media_previews=_media_previews([("Image", link.img)]),
        page_title=link.name or "Link",
        recent_links=_recent_link_links(exclude_link_id=link.id),
        subtitle=link.url,
        tags=link.tags,
    )


@bp.route("/admin/links/<int:link_id>/edit", methods=["GET", "POST"])
def admin_link_edit_route(link_id: int) -> str | Any:
    link = _get_or_404(GroupExternalUrl, link_id)
    if request.method == "POST":
        try:
            update_group_link(
                link,
                group=_optional_related_record(Group, "group_id"),
                route=_optional_related_record(Route, "route_id"),
                name=_form_optional_str("name"),
                url=_form_optional_str("url"),
                link_type=_form_optional_str("type"),
                subtype=_form_optional_str("subtype"),
                description=_form_optional_str("description"),
                tags=_form_csv_list("tags"),
                icon=_form_optional_str("icon"),
                img=_form_optional_str("img"),
            )
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Link saved.", "success")
            return redirect(url_for("core.admin_link_detail_route", link_id=link.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=url_for("core.admin_link_detail_route", link_id=link.id),
        entity_id=link.id,
        entity_type_label="Link",
        fields=_link_fields(link),
        intro_text="Adjust the shared external-link metadata used across groups and routes.",
        mode_title="Edit",
        page_title=link.name or "Link",
        submit_label="Save Changes",
    )


@bp.route("/admin/links/new", methods=["GET", "POST"])
def admin_link_new_route() -> str | Any:
    if request.method == "POST":
        try:
            group = _optional_related_record(Group, "group_id")
            route = _optional_related_record(Route, "route_id")
            if group is None and route is None:
                raise AdminFormError("Either group id or route id is required.")
            if group is not None and route is not None:
                raise AdminFormError("Choose either a group id or a route id, not both.")

            if route is not None:
                link = add_route_link(
                    route,
                    name=_form_required_str("name"),
                    url=_form_required_str("url"),
                    link_type=_form_optional_str("type") or "website",
                    tags=_form_csv_list("tags"),
                )
            else:
                link = add_group_link(
                    cast(Group, group),
                    name=_form_required_str("name"),
                    url=_form_required_str("url"),
                    link_type=_form_optional_str("type") or "website",
                    tags=_form_csv_list("tags"),
                )

            update_group_link(
                link,
                group=group,
                route=route,
                name=_form_required_str("name"),
                url=_form_required_str("url"),
                link_type=_form_optional_str("type"),
                subtype=_form_optional_str("subtype"),
                description=_form_optional_str("description"),
                tags=_form_csv_list("tags"),
                icon=_form_optional_str("icon"),
                img=_form_optional_str("img"),
            )
        except (AdminFormError, ValueError) as exc:
            flash(str(exc), "error")
        else:
            flash("Link created.", "success")
            return redirect(url_for("core.admin_link_detail_route", link_id=link.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=None,
        entity_id=None,
        entity_type_label="Link",
        fields=_link_fields(None),
        intro_text="Create a shared external link for either a group or a route.",
        mode_title="Create",
        page_title="Link",
        submit_label="Create Link",
    )


@bp.get("/admin/dues")
def admin_dues_list_route() -> str:
    dues_entries = list(db.session.scalars(select(GroupDues).order_by(GroupDues.id)))
    return render_template(
        "admin/collection.html",
        page_title="Dues",
        intro_text="Manage group dues definitions and member-payment metadata.",
        new_url=url_for("core.admin_dues_new_route"),
        records=[_dashboard_dues_item(dues) for dues in dues_entries],
    )


@bp.get("/admin/dues/<int:dues_id>")
def admin_dues_detail_route(dues_id: int) -> str:
    dues = _get_or_404(GroupDues, dues_id)
    return render_template(
        "admin/detail.html",
        detail_rows=_detail_rows(
            [
                ("Group ID", dues.group_id, _admin_detail_url("group", dues.group_id)),
                ("Fee", dues.fee),
                ("Duration", dues.duration),
                ("Description", dues.description),
            ]
        ),
        entity_id=dues.id,
        entity_type_label="Dues",
        edit_url=url_for("core.admin_dues_edit_route", dues_id=dues.id),
        location=None,
        media_previews=None,
        page_title=dues.name or "Dues",
        recent_links=_recent_dues_links(exclude_dues_id=dues.id),
        subtitle=f"Group {dues.group_id}" if dues.group_id else None,
        tags=dues.tags,
    )


@bp.route("/admin/dues/<int:dues_id>/edit", methods=["GET", "POST"])
def admin_dues_edit_route(dues_id: int) -> str | Any:
    dues = _get_or_404(GroupDues, dues_id)
    if request.method == "POST":
        try:
            update_group_dues(
                dues,
                group=_required_related_record(Group, "group_id"),
                name=_form_optional_str("name"),
                fee=_form_optional_float("fee"),
                duration=_form_optional_int("duration"),
                description=_form_optional_str("description"),
                tags=_form_csv_list("tags"),
            )
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Dues saved.", "success")
            return redirect(url_for("core.admin_dues_detail_route", dues_id=dues.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=url_for("core.admin_dues_detail_route", dues_id=dues.id),
        entity_id=dues.id,
        entity_type_label="Dues",
        fields=_dues_fields(dues),
        intro_text="Adjust group dues settings from the admin UI.",
        mode_title="Edit",
        page_title=dues.name or "Dues",
        submit_label="Save Changes",
    )


@bp.route("/admin/dues/new", methods=["GET", "POST"])
def admin_dues_new_route() -> str | Any:
    if request.method == "POST":
        try:
            dues = add_group_dues(
                _required_related_record(Group, "group_id"),
                name=_form_required_str("name"),
                fee=_form_required_float("fee"),
                duration=_form_required_int("duration"),
                description=_form_optional_str("description"),
                tags=_form_csv_list("tags"),
            )
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Dues created.", "success")
            return redirect(url_for("core.admin_dues_detail_route", dues_id=dues.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=None,
        entity_id=None,
        entity_type_label="Dues",
        fields=_dues_fields(None),
        intro_text="Create a new group dues definition from the admin UI.",
        mode_title="Create",
        page_title="Dues",
        submit_label="Create Dues",
    )


@bp.get("/admin/fees")
def admin_fee_list_route() -> str:
    fees = list(db.session.scalars(select(EventFee).order_by(EventFee.id)))
    return render_template(
        "admin/collection.html",
        page_title="Fees",
        intro_text="Manage event fee definitions and registration costs.",
        new_url=url_for("core.admin_fee_new_route"),
        records=[_dashboard_fee_item(fee) for fee in fees],
    )


@bp.get("/admin/fees/<int:fee_id>")
def admin_fee_detail_route(fee_id: int) -> str:
    fee = _get_or_404(EventFee, fee_id)
    return render_template(
        "admin/detail.html",
        detail_rows=_detail_rows(
            [
                ("Event ID", fee.event_id, _admin_detail_url("event", fee.event_id)),
                ("Fee", fee.fee),
                ("Duration", fee.duration),
                ("Description", fee.description),
            ]
        ),
        entity_id=fee.id,
        entity_type_label="Fee",
        edit_url=url_for("core.admin_fee_edit_route", fee_id=fee.id),
        location=None,
        media_previews=None,
        page_title=fee.name or "Fee",
        recent_links=_recent_fee_links(exclude_fee_id=fee.id),
        subtitle=f"Event {fee.event_id}" if fee.event_id else None,
        tags=fee.tags,
    )


@bp.route("/admin/fees/<int:fee_id>/edit", methods=["GET", "POST"])
def admin_fee_edit_route(fee_id: int) -> str | Any:
    fee = _get_or_404(EventFee, fee_id)
    if request.method == "POST":
        try:
            update_event_fee(
                fee,
                event=_required_related_record(Event, "event_id"),
                name=_form_optional_str("name"),
                fee=_form_optional_float("fee"),
                duration=_form_optional_int("duration"),
                description=_form_optional_str("description"),
                tags=_form_csv_list("tags"),
            )
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Fee saved.", "success")
            return redirect(url_for("core.admin_fee_detail_route", fee_id=fee.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=url_for("core.admin_fee_detail_route", fee_id=fee.id),
        entity_id=fee.id,
        entity_type_label="Fee",
        fields=_fee_fields(fee),
        intro_text="Adjust event fee settings from the admin UI.",
        mode_title="Edit",
        page_title=fee.name or "Fee",
        submit_label="Save Changes",
    )


@bp.route("/admin/fees/new", methods=["GET", "POST"])
def admin_fee_new_route() -> str | Any:
    if request.method == "POST":
        try:
            fee = add_event_fee(
                _required_related_record(Event, "event_id"),
                name=_form_required_str("name"),
                fee=_form_required_float("fee"),
                duration=_form_required_int("duration"),
                description=_form_optional_str("description"),
                tags=_form_csv_list("tags"),
            )
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Fee created.", "success")
            return redirect(url_for("core.admin_fee_detail_route", fee_id=fee.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=None,
        entity_id=None,
        entity_type_label="Fee",
        fields=_fee_fields(None),
        intro_text="Create a new event fee from the admin UI.",
        mode_title="Create",
        page_title="Fee",
        submit_label="Create Fee",
    )


@bp.get("/admin/groups/<int:group_id>")
def admin_group_detail_route(group_id: int) -> str:
    group = _get_or_404(Group, group_id)
    return render_template(
        "admin/detail.html",
        detail_rows=_detail_rows(
            [
                ("Shortname", group.shortname),
                ("Contact", group.contact),
                ("About", group.about_blurb),
                ("Category", group.category),
                ("Primary activity", group.primary_activity),
                ("More info URL", group.more_info_url),
                ("Member records", len(group.members)),
                ("Linked routes", len(group.routes)),
                ("Links", len(group.links)),
                ("Dues entries", len(group.dues_schedule)),
            ]
        ),
        entity_id=group.id,
        entity_type_label="Group",
        edit_url=url_for("core.admin_group_edit_route", group_id=group.id),
        location=_join_location(group.home_town, group.home_state, group.home_country),
        media_previews=_media_previews(
            [("Hero photo", group.hero_photo.img_medium if group.hero_photo else None)]
        ),
        page_title=group.name or "Group",
        recent_links=_recent_activity_links(exclude=("group", group.id)),
        subtitle=group.shortname or group.primary_activity or group.type,
        tags=_combine_tags(
            group.tags, group.preference_tags, group.rider_classes, group.ride_classes
        ),
    )


@bp.route("/admin/groups/<int:group_id>/edit", methods=["GET", "POST"])
def admin_group_edit_route(group_id: int) -> str | Any:
    group = _get_or_404(Group, group_id)
    if request.method == "POST":
        try:
            update_group(
                group,
                name=_form_required_str("name"),
                shortname=_form_optional_str("shortname"),
                invite_only=_form_bool("invite_only"),
                private=_form_bool("private"),
                home_town=_form_optional_str("home_town"),
                home_state=_form_optional_str("home_state"),
                home_country=_form_optional_str("home_country"),
                home_latlng=_form_optional_str("home_latlng"),
                home_add=_form_optional_str("home_add"),
                full_address=_form_optional_str("full_address"),
                geoll=_form_optional_str("geoll"),
                about_blurb=_form_optional_str("about_blurb"),
                contact=_form_optional_str("contact"),
                category=_form_optional_str("category"),
                primary_activity=_form_optional_str("primary_activity"),
                more_info_url=_form_optional_str("more_info_url"),
                preference_tags=_form_csv_list("preference_tags"),
                tags=_form_csv_list("tags"),
                rider_classes=_form_csv_list("rider_classes"),
                ride_classes=_form_csv_list("ride_classes"),
            )
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Group saved.", "success")
            return redirect(url_for("core.admin_group_detail_route", group_id=group.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=url_for("core.admin_group_detail_route", group_id=group.id),
        entity_id=group.id,
        entity_type_label="Group",
        fields=[
            _edit_text_field("name", "Name", group.name),
            _edit_text_field("shortname", "Shortname", group.shortname),
            _edit_checkbox_field("invite_only", "Invite only", group.invite_only),
            _edit_checkbox_field("private", "Private", group.private),
            _edit_textarea_field("about_blurb", "About", group.about_blurb, rows=6),
            _edit_text_field("contact", "Contact", group.contact),
            _edit_text_field("category", "Category", group.category),
            _edit_text_field("primary_activity", "Primary activity", group.primary_activity),
            _edit_text_field("more_info_url", "More info URL", group.more_info_url),
            _edit_text_field("home_town", "Home town", group.home_town),
            _edit_text_field("home_state", "Home state", group.home_state),
            _edit_text_field("home_country", "Home country", group.home_country),
            _edit_text_field("home_latlng", "Home latlng", group.home_latlng),
            _edit_text_field("home_add", "Home address", group.home_add),
            _edit_text_field("full_address", "Full address", group.full_address),
            _edit_text_field("geoll", "Geometry", group.geoll),
            _edit_text_field("tags", "Tags (comma separated)", _csv_value(group.tags)),
            _edit_text_field(
                "preference_tags",
                "Preference tags (comma separated)",
                _csv_value(group.preference_tags),
            ),
            _edit_text_field(
                "rider_classes",
                "Rider classes (comma separated)",
                _csv_value(group.rider_classes),
            ),
            _edit_text_field(
                "ride_classes",
                "Ride classes (comma separated)",
                _csv_value(group.ride_classes),
            ),
        ],
        intro_text=(
            "Make a focused change to this group and the admin/search surface "
            "will update automatically."
        ),
        mode_title="Edit",
        page_title=group.name or "Group",
        submit_label="Save Changes",
    )


@bp.route("/admin/groups/new", methods=["GET", "POST"])
def admin_group_new_route() -> str | Any:
    if request.method == "POST":
        try:
            group = create_group(
                name=_form_required_str("name"),
                shortname=_form_required_str("shortname"),
                invite_only=_form_bool("invite_only"),
                private=_form_bool("private"),
                home_town=_form_optional_str("home_town"),
                home_state=_form_optional_str("home_state"),
                home_country=_form_optional_str("home_country"),
                home_latlng=_form_optional_str("home_latlng"),
                home_add=_form_optional_str("home_add"),
                full_address=_form_optional_str("full_address"),
                geoll=_form_optional_str("geoll"),
                preference_tags=_form_csv_list("preference_tags"),
                tags=_form_csv_list("tags"),
                rider_classes=_form_csv_list("rider_classes"),
                ride_classes=_form_csv_list("ride_classes"),
            )
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Group created.", "success")
            return redirect(url_for("core.admin_group_detail_route", group_id=group.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=None,
        entity_id=None,
        entity_type_label="Group",
        fields=[
            _edit_text_field("name", "Name", None),
            _edit_text_field("shortname", "Shortname", None),
            _edit_checkbox_field("invite_only", "Invite only", False),
            _edit_checkbox_field("private", "Private", False),
            _edit_text_field("home_town", "Home town", None),
            _edit_text_field("home_state", "Home state", None),
            _edit_text_field("home_country", "Home country", None),
            _edit_text_field("home_latlng", "Home latlng", None),
            _edit_text_field("home_add", "Home address", None),
            _edit_text_field("full_address", "Full address", None),
            _edit_text_field("geoll", "Geometry", None),
            _edit_text_field("tags", "Tags (comma separated)", None),
            _edit_text_field("preference_tags", "Preference tags (comma separated)", None),
            _edit_text_field("rider_classes", "Rider classes (comma separated)", None),
            _edit_text_field("ride_classes", "Ride classes (comma separated)", None),
        ],
        intro_text="Create a new group record from the browser-based admin UI.",
        mode_title="Create",
        page_title="Group",
        submit_label="Create Group",
    )


@bp.get("/admin/routes/<int:route_id>")
def admin_route_detail_route(route_id: int) -> str:
    route = _get_or_404(Route, route_id)
    return render_template(
        "admin/detail.html",
        detail_rows=_detail_rows(
            [
                ("Length", route.length),
                ("Duration", route.duration),
                ("Elevation gain", route.elevation_gain),
                ("Grade", route.grade),
                ("Rating", route.rating),
                ("Type", route.type),
                ("Subtype", route.subtype),
                ("Private", route.private),
                ("Source", route.src),
                ("Source ID", route.src_id),
                ("Athlete ID", route.athlete_id),
                ("Creator ID", route.creator_id),
                ("Address", route.address),
                (
                    "Start coordinates",
                    _coordinate_pair(route.start_latitude, route.start_longitude),
                ),
                ("End coordinates", _coordinate_pair(route.end_latitude, route.end_longitude)),
                ("Elevation profile", route.elevation_array),
                ("Summary polyline", route.summary_polyline),
                ("Full track", route.full_track),
                ("Created", route.init_date),
                ("Updated", route.update_date),
                ("Linked groups", len(route.groups)),
                ("Linked segments", len(route.segments)),
                ("External links", len(route.links)),
            ]
        ),
        entity_id=route.id,
        entity_type_label="Route",
        edit_url=url_for("core.admin_route_edit_route", route_id=route.id),
        location=_join_location(route.city, route.state, route.country),
        media_previews=_route_media_previews(route),
        page_title=route.name or "Route",
        recent_links=_recent_activity_links(exclude=("route", route.id)),
        related_sections=_route_related_sections(route),
        story_sections=_route_story_sections(route),
        subtitle=route.subtype or route.type,
        tags=route.tags,
        stats_bar=_route_stats_bar(route),
        visual_sections=_route_visual_sections(route),
    )


@bp.route("/admin/routes/<int:route_id>/edit", methods=["GET", "POST"])
def admin_route_edit_route(route_id: int) -> str | Any:
    route = _get_or_404(Route, route_id)
    if request.method == "POST":
        try:
            update_route(
                route,
                name=_form_required_str("name"),
                desc=_form_optional_str("desc"),
                private=_form_optional_nullable_bool("private"),
                duration=_form_optional_float("duration"),
                length=_form_optional_float("length"),
                elevation_gain=_form_optional_float("elevation_gain"),
                tags=_form_csv_list("tags"),
                elevation_array=_form_csv_float_list("elevation_array"),
                route_type=_form_optional_str("type"),
                subtype=_form_optional_str("subtype"),
                src=_form_optional_str("src"),
                src_id=_form_optional_str("src_id"),
                start_latitude=_form_optional_float("start_latitude"),
                start_longitude=_form_optional_float("start_longitude"),
                end_latitude=_form_optional_float("end_latitude"),
                end_longitude=_form_optional_float("end_longitude"),
                summary_polyline=_form_optional_str("summary_polyline"),
                full_track=_form_optional_str("full_track"),
                city=_form_optional_str("city"),
                state=_form_optional_str("state"),
                country=_form_optional_str("country"),
                address=_form_optional_str("address"),
                map_thumbnail=_form_optional_str("map_thumbnail"),
            )
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Route saved.", "success")
            return redirect(url_for("core.admin_route_detail_route", route_id=route.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=url_for("core.admin_route_detail_route", route_id=route.id),
        entity_id=route.id,
        entity_type_label="Route",
        fields=[
            _edit_text_field("name", "Name", route.name),
            _edit_textarea_field("desc", "Description", route.desc),
            _edit_text_field(
                "private", "Private (true/false)", _nullable_bool_value(route.private)
            ),
            _edit_text_field("type", "Type", route.type),
            _edit_text_field("subtype", "Subtype", route.subtype),
            _edit_text_field("duration", "Duration", route.duration),
            _edit_text_field("length", "Length", route.length),
            _edit_text_field("elevation_gain", "Elevation gain", route.elevation_gain),
            _edit_text_field(
                "elevation_array",
                "Elevation array (comma separated)",
                _csv_number_value(route.elevation_array),
            ),
            _edit_text_field("src", "Source", route.src),
            _edit_text_field("src_id", "Source ID", route.src_id),
            _edit_text_field("city", "City", route.city),
            _edit_text_field("state", "State", route.state),
            _edit_text_field("country", "Country", route.country),
            _edit_text_field("address", "Address", route.address),
            _edit_text_field("map_thumbnail", "Map thumbnail", route.map_thumbnail),
            _edit_text_field("start_latitude", "Start latitude", route.start_latitude),
            _edit_text_field("start_longitude", "Start longitude", route.start_longitude),
            _edit_text_field("end_latitude", "End latitude", route.end_latitude),
            _edit_text_field("end_longitude", "End longitude", route.end_longitude),
            _edit_text_field("tags", "Tags (comma separated)", _csv_value(route.tags)),
            _edit_textarea_field("summary_polyline", "Summary polyline", route.summary_polyline),
            _edit_textarea_field("full_track", "Full track", route.full_track),
        ],
        intro_text="Tune route metadata from the admin UI without leaving the browser.",
        mode_title="Edit",
        page_title=route.name or "Route",
        submit_label="Save Changes",
    )


@bp.route("/admin/routes/new", methods=["GET", "POST"])
def admin_route_new_route() -> str | Any:
    if request.method == "POST":
        try:
            route = create_route(
                name=_form_required_str("name"),
                desc=_form_optional_str("desc"),
                private=_form_optional_nullable_bool("private"),
                duration=_form_optional_float("duration"),
                length=_form_optional_float("length"),
                elevation_gain=_form_optional_float("elevation_gain"),
                tags=_form_csv_list("tags"),
                elevation_array=_form_csv_float_list("elevation_array"),
                route_type=_form_optional_str("type"),
                subtype=_form_optional_str("subtype"),
                src=_form_optional_str("src"),
                src_id=_form_optional_str("src_id"),
                start_latitude=_form_optional_float("start_latitude"),
                start_longitude=_form_optional_float("start_longitude"),
                end_latitude=_form_optional_float("end_latitude"),
                end_longitude=_form_optional_float("end_longitude"),
                summary_polyline=_form_optional_str("summary_polyline"),
                full_track=_form_optional_str("full_track"),
                city=_form_optional_str("city"),
                state=_form_optional_str("state"),
                country=_form_optional_str("country"),
                address=_form_optional_str("address"),
                map_thumbnail=_form_optional_str("map_thumbnail"),
            )
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Route created.", "success")
            return redirect(url_for("core.admin_route_detail_route", route_id=route.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=None,
        entity_id=None,
        entity_type_label="Route",
        fields=[
            _edit_text_field("name", "Name", None),
            _edit_textarea_field("desc", "Description", None),
            _edit_text_field("private", "Private (true/false)", None),
            _edit_text_field("type", "Type", None),
            _edit_text_field("subtype", "Subtype", None),
            _edit_text_field("duration", "Duration", None),
            _edit_text_field("length", "Length", None),
            _edit_text_field("elevation_gain", "Elevation gain", None),
            _edit_text_field("elevation_array", "Elevation array (comma separated)", None),
            _edit_text_field("src", "Source", None),
            _edit_text_field("src_id", "Source ID", None),
            _edit_text_field("city", "City", None),
            _edit_text_field("state", "State", None),
            _edit_text_field("country", "Country", None),
            _edit_text_field("address", "Address", None),
            _edit_text_field("map_thumbnail", "Map thumbnail", None),
            _edit_text_field("start_latitude", "Start latitude", None),
            _edit_text_field("start_longitude", "Start longitude", None),
            _edit_text_field("end_latitude", "End latitude", None),
            _edit_text_field("end_longitude", "End longitude", None),
            _edit_text_field("tags", "Tags (comma separated)", None),
            _edit_textarea_field("summary_polyline", "Summary polyline", None),
            _edit_textarea_field("full_track", "Full track", None),
        ],
        intro_text=(
            "Create a new route record and immediately make it available in "
            "search and admin drill-down views."
        ),
        mode_title="Create",
        page_title="Route",
        submit_label="Create Route",
    )


@bp.get("/admin/segments/<int:segment_id>")
def admin_segment_detail_route(segment_id: int) -> str:
    segment = _get_or_404(Segment, segment_id)
    return render_template(
        "admin/detail.html",
        detail_rows=_detail_rows(
            [
                ("Length", segment.length),
                ("Duration", segment.duration),
                ("Elevation gain", segment.elevation_gain),
                ("Grade", segment.grade),
                ("Rating", segment.rating),
                ("Type", segment.type),
                ("Subtype", segment.subtype),
                ("Elevation loss", segment.elevation_loss),
                ("Elevation high", segment.elev_high),
                ("Elevation low", segment.elev_low),
                ("Source", segment.src),
                ("Source ID", segment.src_id),
                ("Source URL", segment.src_url, segment.src_url),
                (
                    "Start coordinates",
                    _coordinate_pair(segment.start_latitude, segment.start_longitude),
                ),
                (
                    "End coordinates",
                    _coordinate_pair(segment.end_latitude, segment.end_longitude),
                ),
                ("Elevation profile", segment.elevation_array),
                ("Summary polyline", segment.summary_polyline),
                ("Full track", segment.full_track),
                ("Track hash", segment.track_hash),
                ("Track max speed", segment.track_maxspeed),
                ("Recorded", segment.record_date),
                ("Created", segment.init_date),
                ("Updated", segment.update_date),
                ("Linked routes", len(segment.routes)),
                ("Linked images", len(segment.images)),
            ]
        ),
        entity_id=segment.id,
        entity_type_label="Segment",
        edit_url=url_for("core.admin_segment_edit_route", segment_id=segment.id),
        location=None,
        media_previews=_segment_media_previews(segment),
        page_title=segment.name or "Segment",
        recent_links=_recent_activity_links(exclude=("segment", segment.id)),
        related_sections=_segment_related_sections(segment),
        story_sections=_segment_story_sections(segment),
        subtitle=segment.subtype or segment.type,
        tags=segment.tags,
        stats_bar=_segment_stats_bar(segment),
        visual_sections=_segment_visual_sections(segment),
    )


@bp.route("/admin/segments/<int:segment_id>/edit", methods=["GET", "POST"])
def admin_segment_edit_route(segment_id: int) -> str | Any:
    segment = _get_or_404(Segment, segment_id)
    if request.method == "POST":
        try:
            update_segment(
                segment,
                name=_form_required_str("name"),
                desc=_form_optional_str("desc"),
                duration=_form_optional_float("duration"),
                length=_form_optional_float("length"),
                elevation_gain=_form_optional_float("elevation_gain"),
                elevation_array=_form_csv_float_list("elevation_array"),
                elevation_loss=_form_optional_float("elevation_loss"),
                elev_high=_form_optional_float("elev_high"),
                elev_low=_form_optional_float("elev_low"),
                rating=_form_optional_float("rating"),
                grade=_form_optional_float("grade"),
                segment_type=_form_optional_str("type"),
                subtype=_form_optional_str("subtype"),
                tags=_form_csv_list("tags"),
                src=_form_optional_str("src"),
                src_id=_form_optional_str("src_id"),
                src_url=_form_optional_str("src_url"),
                start_latitude=_form_optional_float("start_latitude"),
                start_longitude=_form_optional_float("start_longitude"),
                end_latitude=_form_optional_float("end_latitude"),
                end_longitude=_form_optional_float("end_longitude"),
                summary_polyline=_form_optional_str("summary_polyline"),
                full_track=_form_optional_str("full_track"),
                track_hash=_form_optional_str("track_hash"),
                track_maxspeed=_form_optional_float("track_maxspeed"),
            )
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Segment saved.", "success")
            return redirect(url_for("core.admin_segment_detail_route", segment_id=segment.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=url_for("core.admin_segment_detail_route", segment_id=segment.id),
        entity_id=segment.id,
        entity_type_label="Segment",
        fields=[
            _edit_text_field("name", "Name", segment.name),
            _edit_textarea_field("desc", "Description", segment.desc),
            _edit_text_field("type", "Type", segment.type),
            _edit_text_field("subtype", "Subtype", segment.subtype),
            _edit_text_field("duration", "Duration", segment.duration),
            _edit_text_field("length", "Length", segment.length),
            _edit_text_field("elevation_gain", "Elevation gain", segment.elevation_gain),
            _edit_text_field(
                "elevation_array",
                "Elevation array (comma separated)",
                _csv_number_value(segment.elevation_array),
            ),
            _edit_text_field("elevation_loss", "Elevation loss", segment.elevation_loss),
            _edit_text_field("elev_high", "Elevation high", segment.elev_high),
            _edit_text_field("elev_low", "Elevation low", segment.elev_low),
            _edit_text_field("rating", "Rating", segment.rating),
            _edit_text_field("grade", "Grade", segment.grade),
            _edit_text_field("src", "Source", segment.src),
            _edit_text_field("src_id", "Source ID", segment.src_id),
            _edit_text_field("src_url", "Source URL", segment.src_url),
            _edit_text_field("start_latitude", "Start latitude", segment.start_latitude),
            _edit_text_field("start_longitude", "Start longitude", segment.start_longitude),
            _edit_text_field("end_latitude", "End latitude", segment.end_latitude),
            _edit_text_field("end_longitude", "End longitude", segment.end_longitude),
            _edit_text_field("tags", "Tags (comma separated)", _csv_value(segment.tags)),
            _edit_textarea_field("summary_polyline", "Summary polyline", segment.summary_polyline),
            _edit_textarea_field("full_track", "Full track", segment.full_track),
            _edit_text_field("track_hash", "Track hash", segment.track_hash),
            _edit_text_field("track_maxspeed", "Track maxspeed", segment.track_maxspeed),
        ],
        intro_text="Adjust segment metadata and keep related search results current.",
        mode_title="Edit",
        page_title=segment.name or "Segment",
        submit_label="Save Changes",
    )


@bp.route("/admin/segments/new", methods=["GET", "POST"])
def admin_segment_new_route() -> str | Any:
    if request.method == "POST":
        try:
            segment = create_segment(
                name=_form_required_str("name"),
                desc=_form_optional_str("desc"),
                duration=_form_optional_float("duration"),
                length=_form_optional_float("length"),
                elevation_gain=_form_optional_float("elevation_gain"),
                elevation_array=_form_csv_float_list("elevation_array"),
                elevation_loss=_form_optional_float("elevation_loss"),
                elev_high=_form_optional_float("elev_high"),
                elev_low=_form_optional_float("elev_low"),
                rating=_form_optional_float("rating"),
                grade=_form_optional_float("grade"),
                segment_type=_form_optional_str("type"),
                subtype=_form_optional_str("subtype"),
                tags=_form_csv_list("tags"),
                src=_form_optional_str("src"),
                src_id=_form_optional_str("src_id"),
                src_url=_form_optional_str("src_url"),
                start_latitude=_form_optional_float("start_latitude"),
                start_longitude=_form_optional_float("start_longitude"),
                end_latitude=_form_optional_float("end_latitude"),
                end_longitude=_form_optional_float("end_longitude"),
                summary_polyline=_form_optional_str("summary_polyline"),
                full_track=_form_optional_str("full_track"),
                track_hash=_form_optional_str("track_hash"),
                track_maxspeed=_form_optional_float("track_maxspeed"),
            )
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Segment created.", "success")
            return redirect(url_for("core.admin_segment_detail_route", segment_id=segment.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=None,
        entity_id=None,
        entity_type_label="Segment",
        fields=[
            _edit_text_field("name", "Name", None),
            _edit_textarea_field("desc", "Description", None),
            _edit_text_field("type", "Type", None),
            _edit_text_field("subtype", "Subtype", None),
            _edit_text_field("duration", "Duration", None),
            _edit_text_field("length", "Length", None),
            _edit_text_field("elevation_gain", "Elevation gain", None),
            _edit_text_field("elevation_array", "Elevation array (comma separated)", None),
            _edit_text_field("elevation_loss", "Elevation loss", None),
            _edit_text_field("elev_high", "Elevation high", None),
            _edit_text_field("elev_low", "Elevation low", None),
            _edit_text_field("rating", "Rating", None),
            _edit_text_field("grade", "Grade", None),
            _edit_text_field("src", "Source", None),
            _edit_text_field("src_id", "Source ID", None),
            _edit_text_field("src_url", "Source URL", None),
            _edit_text_field("start_latitude", "Start latitude", None),
            _edit_text_field("start_longitude", "Start longitude", None),
            _edit_text_field("end_latitude", "End latitude", None),
            _edit_text_field("end_longitude", "End longitude", None),
            _edit_text_field("tags", "Tags (comma separated)", None),
            _edit_textarea_field("summary_polyline", "Summary polyline", None),
            _edit_textarea_field("full_track", "Full track", None),
            _edit_text_field("track_hash", "Track hash", None),
            _edit_text_field("track_maxspeed", "Track maxspeed", None),
        ],
        intro_text="Create a new segment from the browser-based admin UI.",
        mode_title="Create",
        page_title="Segment",
        submit_label="Create Segment",
    )


@bp.get("/admin/events/<int:event_id>")
def admin_event_detail_route(event_id: int) -> str:
    event = _get_or_404(Event, event_id)
    return render_template(
        "admin/detail.html",
        detail_rows=_detail_rows(
            [
                ("Starts", event.date_start),
                ("Ends", event.date_end),
                ("Duration", event.duration),
                ("Primary activity", event.primary_activity),
                ("Type", event.type),
                ("Subtype", event.subtype),
                ("Private", event.private),
                ("Email", event.email),
                ("URL", event.url, event.url),
                ("Registration URL", event.reg_url, event.reg_url),
                ("Notes", event.notes),
                ("Latitude", event.lat),
                ("Longitude", event.lon),
                ("Latlng", event.latlng),
                ("Geometry", event.geoll),
                ("Created", event.date_created),
                ("Updated", event.date_updated),
                ("Route ID", event.route_id, _admin_detail_url("route", event.route_id)),
                (
                    "Activity ID",
                    event.activity_id,
                    _admin_detail_url("activity", event.activity_id),
                ),
                ("Calendars", len(event.calendars)),
                ("Images", len(event.images)),
                ("Participants", len(event.participants)),
            ]
        ),
        entity_id=event.id,
        entity_type_label="Event",
        edit_url=url_for("core.admin_event_edit_route", event_id=event.id),
        location=_join_location(event.town, event.state, event.country),
        media_previews=_event_media_previews(event),
        page_title=event.name or "Event",
        recent_links=_recent_activity_links(exclude=("event", event.id)),
        related_sections=_event_related_sections(event),
        stats_bar=_event_stats_bar(event),
        story_sections=_event_story_sections(event),
        subtitle=event.subtype or event.type or event.primary_activity,
        tags=event.tags,
        visual_sections=_event_visual_sections(event),
    )


@bp.route("/admin/events/<int:event_id>/edit", methods=["GET", "POST"])
def admin_event_edit_route(event_id: int) -> str | Any:
    event = _get_or_404(Event, event_id)
    if request.method == "POST":
        try:
            route = _optional_related_record(Route, "route_id")
            activity = _optional_related_record(Activity, "activity_id")
            update_event(
                event,
                name=_form_required_str("name"),
                route=route,
                activity=activity,
                private=_form_bool("private"),
                description=_form_optional_str("description"),
                url=_form_optional_str("url"),
                reg_url=_form_optional_str("reg_url"),
                photo_url=_form_optional_str("photo_url"),
                logo=_form_optional_str("logo"),
                profile_photo=_form_optional_str("profile_photo"),
                notes=_form_optional_str("notes"),
                tags=_form_csv_list("tags"),
                lat=_form_optional_float("lat"),
                lon=_form_optional_float("lon"),
                town=_form_optional_str("town"),
                state=_form_optional_str("state"),
                country=_form_optional_str("country"),
                latlng=_form_optional_str("latlng"),
                geoll=_form_optional_str("geoll"),
                primary_activity=_form_optional_str("primary_activity"),
                event_type=_form_optional_str("type"),
                subtype=_form_optional_str("subtype"),
            )
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Event saved.", "success")
            return redirect(url_for("core.admin_event_detail_route", event_id=event.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=url_for("core.admin_event_detail_route", event_id=event.id),
        entity_id=event.id,
        entity_type_label="Event",
        fields=[
            _edit_text_field("name", "Name", event.name),
            _edit_checkbox_field("private", "Private", event.private),
            _edit_textarea_field("description", "Description", event.description),
            _edit_text_field("primary_activity", "Primary activity", event.primary_activity),
            _edit_text_field("type", "Type", event.type),
            _edit_text_field("subtype", "Subtype", event.subtype),
            _edit_related_field(
                "route_id",
                "Route ID",
                event.route_id,
                model=Route,
                title_getter=lambda route: route.name or "Route",
            ),
            _edit_related_field(
                "activity_id",
                "Activity ID",
                event.activity_id,
                model=Activity,
                title_getter=lambda activity: activity.name or "Activity",
            ),
            _edit_text_field("url", "URL", event.url),
            _edit_text_field("reg_url", "Registration URL", event.reg_url),
            _edit_text_field("photo_url", "Photo URL", event.photo_url),
            _edit_text_field("logo", "Logo", event.logo),
            _edit_text_field("profile_photo", "Profile photo", event.profile_photo),
            _edit_textarea_field("notes", "Notes", event.notes),
            _edit_text_field("town", "Town", event.town),
            _edit_text_field("state", "State", event.state),
            _edit_text_field("country", "Country", event.country),
            _edit_text_field("lat", "Latitude", event.lat),
            _edit_text_field("lon", "Longitude", event.lon),
            _edit_text_field("latlng", "Latlng", event.latlng),
            _edit_text_field("geoll", "Geometry", event.geoll),
            _edit_text_field("tags", "Tags (comma separated)", _csv_value(event.tags)),
        ],
        intro_text="Adjust event details and keep the admin/search layer aligned automatically.",
        mode_title="Edit",
        page_title=event.name or "Event",
        submit_label="Save Changes",
    )


@bp.route("/admin/events/new", methods=["GET", "POST"])
def admin_event_new_route() -> str | Any:
    if request.method == "POST":
        try:
            route = _optional_related_record(Route, "route_id")
            activity = _optional_related_record(Activity, "activity_id")
            event = create_event(
                name=_form_required_str("name"),
                route=route,
                activity=activity,
                private=_form_bool("private"),
                description=_form_optional_str("description"),
                url=_form_optional_str("url"),
                reg_url=_form_optional_str("reg_url"),
                photo_url=_form_optional_str("photo_url"),
                logo=_form_optional_str("logo"),
                profile_photo=_form_optional_str("profile_photo"),
                notes=_form_optional_str("notes"),
                tags=_form_csv_list("tags"),
                lat=_form_optional_float("lat"),
                lon=_form_optional_float("lon"),
                town=_form_optional_str("town"),
                state=_form_optional_str("state"),
                country=_form_optional_str("country"),
                latlng=_form_optional_str("latlng"),
                geoll=_form_optional_str("geoll"),
            )
            event.primary_activity = _form_optional_str("primary_activity")
            event.type = _form_optional_str("type")
            event.subtype = _form_optional_str("subtype")
            db.session.commit()
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Event created.", "success")
            return redirect(url_for("core.admin_event_detail_route", event_id=event.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=None,
        entity_id=None,
        entity_type_label="Event",
        fields=[
            _edit_text_field("name", "Name", None),
            _edit_checkbox_field("private", "Private", False),
            _edit_textarea_field("description", "Description", None),
            _edit_text_field("primary_activity", "Primary activity", None),
            _edit_text_field("type", "Type", None),
            _edit_text_field("subtype", "Subtype", None),
            _edit_related_field(
                "route_id",
                "Route ID",
                None,
                model=Route,
                title_getter=lambda route: route.name or "Route",
            ),
            _edit_related_field(
                "activity_id",
                "Activity ID",
                None,
                model=Activity,
                title_getter=lambda activity: activity.name or "Activity",
            ),
            _edit_text_field("url", "URL", None),
            _edit_text_field("reg_url", "Registration URL", None),
            _edit_text_field("photo_url", "Photo URL", None),
            _edit_text_field("logo", "Logo", None),
            _edit_text_field("profile_photo", "Profile photo", None),
            _edit_textarea_field("notes", "Notes", None),
            _edit_text_field("town", "Town", None),
            _edit_text_field("state", "State", None),
            _edit_text_field("country", "Country", None),
            _edit_text_field("lat", "Latitude", None),
            _edit_text_field("lon", "Longitude", None),
            _edit_text_field("latlng", "Latlng", None),
            _edit_text_field("geoll", "Geometry", None),
            _edit_text_field("tags", "Tags (comma separated)", None),
        ],
        intro_text=(
            "Create a new event from the browser-based admin UI and jump "
            "straight into its detail page."
        ),
        mode_title="Create",
        page_title="Event",
        submit_label="Create Event",
    )


@bp.get("/admin/points-of-interest/<int:point_id>")
def admin_point_of_interest_detail_route(point_id: int) -> str:
    point = _get_or_404(PointOfInterest, point_id)
    return render_template(
        "admin/detail.html",
        detail_rows=_detail_rows(
            [
                ("Type", point.type),
                ("Subtype", point.subtype),
                ("Latitude", point.lat),
                ("Longitude", point.lon),
                ("Coordinates", _coordinate_pair(point.lat, point.lon)),
                ("Geometry", point.geoll),
                ("URL", point.url, point.url),
                ("Icon", point.icon),
                ("Owner ID", point.owner_id),
                ("Created", point.date_created),
                ("Updated", point.date_updated),
                ("Images", len(point.images)),
            ]
        ),
        entity_id=point.id,
        entity_type_label="Point of Interest",
        edit_url=url_for("core.admin_point_of_interest_edit_route", point_id=point.id),
        location=None,
        media_previews=_point_of_interest_media_previews(point),
        page_title=point.name or "Point of Interest",
        recent_links=_recent_activity_links(exclude=("point_of_interest", point.id)),
        related_sections=_point_of_interest_related_sections(point),
        story_sections=_point_of_interest_story_sections(point),
        subtitle=point.subtype or point.type,
        tags=point.tags,
    )


@bp.route("/admin/points-of-interest/<int:point_id>/edit", methods=["GET", "POST"])
def admin_point_of_interest_edit_route(point_id: int) -> str | Any:
    point = _get_or_404(PointOfInterest, point_id)
    if request.method == "POST":
        try:
            update_point_of_interest(
                point,
                name=_form_required_str("name"),
                poi_type=_form_optional_str("type"),
                subtype=_form_optional_str("subtype"),
                lat=_form_optional_float("lat"),
                lon=_form_optional_float("lon"),
                geoll=_form_optional_str("geoll"),
                url=_form_optional_str("url"),
                description=_form_optional_str("description"),
                tags=_form_csv_list("tags"),
                icon=_form_optional_str("icon"),
            )
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Point of interest saved.", "success")
            return redirect(url_for("core.admin_point_of_interest_detail_route", point_id=point.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=url_for("core.admin_point_of_interest_detail_route", point_id=point.id),
        entity_id=point.id,
        entity_type_label="Point of Interest",
        fields=[
            _edit_text_field("name", "Name", point.name),
            _edit_text_field("type", "Type", point.type),
            _edit_text_field("subtype", "Subtype", point.subtype),
            _edit_text_field("lat", "Latitude", point.lat),
            _edit_text_field("lon", "Longitude", point.lon),
            _edit_text_field("geoll", "Geometry", point.geoll),
            _edit_text_field("url", "URL", point.url),
            _edit_textarea_field("description", "Description", point.description),
            _edit_text_field("tags", "Tags (comma separated)", _csv_value(point.tags)),
            _edit_text_field("icon", "Icon", point.icon),
        ],
        intro_text="Adjust a point of interest and keep search/admin views aligned.",
        mode_title="Edit",
        page_title=point.name or "Point of Interest",
        submit_label="Save Changes",
    )


@bp.route("/admin/points-of-interest/new", methods=["GET", "POST"])
def admin_point_of_interest_new_route() -> str | Any:
    if request.method == "POST":
        try:
            point = create_point_of_interest(
                name=_form_required_str("name"),
                poi_type=_form_optional_str("type"),
                subtype=_form_optional_str("subtype"),
                lat=_form_optional_float("lat"),
                lon=_form_optional_float("lon"),
                geoll=_form_optional_str("geoll"),
                url=_form_optional_str("url"),
                description=_form_optional_str("description"),
                tags=_form_csv_list("tags"),
                icon=_form_optional_str("icon"),
            )
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Point of interest created.", "success")
            return redirect(url_for("core.admin_point_of_interest_detail_route", point_id=point.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=None,
        entity_id=None,
        entity_type_label="Point of Interest",
        fields=[
            _edit_text_field("name", "Name", None),
            _edit_text_field("type", "Type", None),
            _edit_text_field("subtype", "Subtype", None),
            _edit_text_field("lat", "Latitude", None),
            _edit_text_field("lon", "Longitude", None),
            _edit_text_field("geoll", "Geometry", None),
            _edit_text_field("url", "URL", None),
            _edit_textarea_field("description", "Description", None),
            _edit_text_field("tags", "Tags (comma separated)", None),
            _edit_text_field("icon", "Icon", None),
        ],
        intro_text="Create a new point of interest from the browser-based admin UI.",
        mode_title="Create",
        page_title="Point of Interest",
        submit_label="Create Point of Interest",
    )


@bp.get("/admin/activities/<int:activity_id>")
def admin_activity_detail_route(activity_id: int) -> str:
    activity = _get_or_404(Activity, activity_id)
    return render_template(
        "admin/detail.html",
        detail_rows=_detail_rows(
            [
                ("Length", activity.length),
                ("Duration", activity.duration),
                ("Elevation gain", activity.elevation_gain),
                ("Average speed", activity.average_speed),
                ("Max speed", activity.max_speed),
                ("Moving time", activity.moving_time),
                ("Total elevation gain", activity.total_elevation_gain),
                ("Elevation high", activity.elev_high),
                ("Elevation low", activity.elev_low),
                ("Type", activity.type),
                ("Subtype", activity.subtype),
                ("Private", activity.private),
                ("Athlete ID", activity.athlete_id),
                ("Source", activity.src),
                ("Source ID", activity.src_id),
                ("Starts", activity.start_date),
                ("Ends", activity.end_date),
                (
                    "Start coordinates",
                    _coordinate_pair(activity.start_latitude, activity.start_longitude),
                ),
                (
                    "End coordinates",
                    _coordinate_pair(activity.end_latitude, activity.end_longitude),
                ),
                ("Summary polyline", activity.summary_polyline),
                ("Full track", activity.full_track),
                ("Created", activity.init_date),
                ("Updated", activity.update_date),
                ("Route ID", activity.route_id, _admin_detail_url("route", activity.route_id)),
                ("Images", len(activity.images)),
            ]
        ),
        entity_id=activity.id,
        entity_type_label="Activity",
        edit_url=url_for("core.admin_activity_edit_route", activity_id=activity.id),
        location=None,
        media_previews=_activity_media_previews(activity),
        page_title=activity.name or "Activity",
        recent_links=_recent_activity_links(exclude=("activity", activity.id)),
        related_sections=_activity_related_sections(activity),
        stats_bar=_activity_stats_bar(activity),
        story_sections=_activity_story_sections(activity),
        subtitle=activity.subtype or activity.type,
        tags=activity.tags,
        visual_sections=_activity_visual_sections(activity),
    )


@bp.route("/admin/activities/<int:activity_id>/edit", methods=["GET", "POST"])
def admin_activity_edit_route(activity_id: int) -> str | Any:
    activity = _get_or_404(Activity, activity_id)
    if request.method == "POST":
        try:
            route = _optional_related_record(Route, "route_id")
            update_activity(
                activity,
                route=route,
                name=_form_required_str("name"),
                desc=_form_optional_str("desc"),
                private=_form_optional_nullable_bool("private"),
                photo_url=_form_optional_str("photo_url"),
                tags=_form_csv_list("tags"),
                duration=_form_optional_float("duration"),
                length=_form_optional_float("length"),
                elevation_gain=_form_optional_float("elevation_gain"),
                average_speed=_form_optional_float("average_speed"),
                max_speed=_form_optional_float("max_speed"),
                moving_time=_form_optional_float("moving_time"),
                total_elevation_gain=_form_optional_float("total_elevation_gain"),
                elev_high=_form_optional_float("elev_high"),
                elev_low=_form_optional_float("elev_low"),
                activity_type=_form_optional_str("type"),
                subtype=_form_optional_str("subtype"),
                src=_form_optional_str("src"),
                src_id=_form_optional_str("src_id"),
                start_latitude=_form_optional_float("start_latitude"),
                start_longitude=_form_optional_float("start_longitude"),
                end_latitude=_form_optional_float("end_latitude"),
                end_longitude=_form_optional_float("end_longitude"),
                summary_polyline=_form_optional_str("summary_polyline"),
                full_track=_form_optional_str("full_track"),
            )
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Activity saved.", "success")
            return redirect(url_for("core.admin_activity_detail_route", activity_id=activity.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=url_for("core.admin_activity_detail_route", activity_id=activity.id),
        entity_id=activity.id,
        entity_type_label="Activity",
        fields=[
            _edit_text_field("name", "Name", activity.name),
            _edit_textarea_field("desc", "Description", activity.desc),
            _edit_text_field(
                "private", "Private (true/false)", _nullable_bool_value(activity.private)
            ),
            _edit_related_field(
                "route_id",
                "Route ID",
                activity.route_id,
                model=Route,
                title_getter=lambda route: route.name or "Route",
            ),
            _edit_text_field("photo_url", "Photo URL", activity.photo_url),
            _edit_text_field("tags", "Tags (comma separated)", _csv_value(activity.tags)),
            _edit_text_field("duration", "Duration", activity.duration),
            _edit_text_field("length", "Length", activity.length),
            _edit_text_field("elevation_gain", "Elevation gain", activity.elevation_gain),
            _edit_text_field("average_speed", "Average speed", activity.average_speed),
            _edit_text_field("max_speed", "Max speed", activity.max_speed),
            _edit_text_field("moving_time", "Moving time", activity.moving_time),
            _edit_text_field(
                "total_elevation_gain", "Total elevation gain", activity.total_elevation_gain
            ),
            _edit_text_field("elev_high", "Elevation high", activity.elev_high),
            _edit_text_field("elev_low", "Elevation low", activity.elev_low),
            _edit_text_field("type", "Type", activity.type),
            _edit_text_field("subtype", "Subtype", activity.subtype),
            _edit_text_field("src", "Source", activity.src),
            _edit_text_field("src_id", "Source ID", activity.src_id),
            _edit_text_field("start_latitude", "Start latitude", activity.start_latitude),
            _edit_text_field("start_longitude", "Start longitude", activity.start_longitude),
            _edit_text_field("end_latitude", "End latitude", activity.end_latitude),
            _edit_text_field("end_longitude", "End longitude", activity.end_longitude),
            _edit_textarea_field("summary_polyline", "Summary polyline", activity.summary_polyline),
            _edit_textarea_field("full_track", "Full track", activity.full_track),
        ],
        intro_text="Adjust activity metadata from the admin UI and keep search in sync.",
        mode_title="Edit",
        page_title=activity.name or "Activity",
        submit_label="Save Changes",
    )


@bp.route("/admin/activities/new", methods=["GET", "POST"])
def admin_activity_new_route() -> str | Any:
    if request.method == "POST":
        try:
            route = _optional_related_record(Route, "route_id")
            activity = create_activity(
                route=route,
                name=_form_required_str("name"),
                desc=_form_optional_str("desc"),
                private=_form_optional_nullable_bool("private"),
                photo_url=_form_optional_str("photo_url"),
                tags=_form_csv_list("tags"),
                duration=_form_optional_float("duration"),
                length=_form_optional_float("length"),
                elevation_gain=_form_optional_float("elevation_gain"),
                average_speed=_form_optional_float("average_speed"),
                max_speed=_form_optional_float("max_speed"),
                moving_time=_form_optional_float("moving_time"),
                total_elevation_gain=_form_optional_float("total_elevation_gain"),
                elev_high=_form_optional_float("elev_high"),
                elev_low=_form_optional_float("elev_low"),
                activity_type=_form_optional_str("type"),
                subtype=_form_optional_str("subtype"),
                src=_form_optional_str("src"),
                src_id=_form_optional_str("src_id"),
                start_latitude=_form_optional_float("start_latitude"),
                start_longitude=_form_optional_float("start_longitude"),
                end_latitude=_form_optional_float("end_latitude"),
                end_longitude=_form_optional_float("end_longitude"),
                summary_polyline=_form_optional_str("summary_polyline"),
                full_track=_form_optional_str("full_track"),
            )
        except AdminFormError as exc:
            flash(str(exc), "error")
        else:
            flash("Activity created.", "success")
            return redirect(url_for("core.admin_activity_detail_route", activity_id=activity.id))

    return render_template(
        "admin/edit.html",
        dashboard_url=url_for("core.admin_dashboard_route"),
        detail_url=None,
        entity_id=None,
        entity_type_label="Activity",
        fields=[
            _edit_text_field("name", "Name", None),
            _edit_textarea_field("desc", "Description", None),
            _edit_text_field("private", "Private (true/false)", None),
            _edit_related_field(
                "route_id",
                "Route ID",
                None,
                model=Route,
                title_getter=lambda route: route.name or "Route",
            ),
            _edit_text_field("photo_url", "Photo URL", None),
            _edit_text_field("tags", "Tags (comma separated)", None),
            _edit_text_field("duration", "Duration", None),
            _edit_text_field("length", "Length", None),
            _edit_text_field("elevation_gain", "Elevation gain", None),
            _edit_text_field("average_speed", "Average speed", None),
            _edit_text_field("max_speed", "Max speed", None),
            _edit_text_field("moving_time", "Moving time", None),
            _edit_text_field("total_elevation_gain", "Total elevation gain", None),
            _edit_text_field("elev_high", "Elevation high", None),
            _edit_text_field("elev_low", "Elevation low", None),
            _edit_text_field("type", "Type", None),
            _edit_text_field("subtype", "Subtype", None),
            _edit_text_field("src", "Source", None),
            _edit_text_field("src_id", "Source ID", None),
            _edit_text_field("start_latitude", "Start latitude", None),
            _edit_text_field("start_longitude", "Start longitude", None),
            _edit_text_field("end_latitude", "End latitude", None),
            _edit_text_field("end_longitude", "End longitude", None),
            _edit_textarea_field("summary_polyline", "Summary polyline", None),
            _edit_textarea_field("full_track", "Full track", None),
        ],
        intro_text="Create a new activity from the browser-based admin UI.",
        mode_title="Create",
        page_title="Activity",
        submit_label="Create Activity",
    )


@bp.post("/api/bootstrap/lookup-rows")
def bootstrap_lookup_rows() -> tuple[dict[str, list[str]], int]:
    return ensure_canonical_lookup_rows(), HTTPStatus.OK


@bp.post("/api/search/reindex")
def rebuild_search_index_route() -> tuple[dict[str, int], int]:
    return {"indexed": rebuild_search_documents()}, HTTPStatus.OK


@bp.get("/api/search")
def search_route() -> tuple[dict[str, object], int]:
    query = request.args.get("q", type=str)
    if query is None or not query.strip():
        abort(HTTPStatus.BAD_REQUEST)

    parsed_types = parse_search_types(request.args.getlist("type"))
    requested_limit = request.args.get("limit", default=25, type=int)
    limit = min(max(requested_limit, 1), 100)
    documents = search_documents(query=query, types=parsed_types or None, limit=limit)
    return {"items": [_search_document_payload(document) for document in documents]}, HTTPStatus.OK


@bp.post("/api/groups")
def create_group_route() -> tuple[dict[str, object], int]:
    payload = _json_payload()
    group = create_group(
        name=_required_str(payload, "name"),
        shortname=_required_str(payload, "shortname"),
        invite_only=_optional_bool(payload, "invite_only", default=False),
        private=_optional_bool(payload, "private", default=False),
        home_town=_optional_str(payload, "home_town"),
        home_state=_optional_str(payload, "home_state"),
        home_country=_optional_str(payload, "home_country"),
        home_latlng=_optional_str(payload, "home_latlng"),
        home_add=_optional_str(payload, "home_add"),
        full_address=_optional_str(payload, "full_address"),
        geoll=_optional_str(payload, "geoll"),
        preference_tags=_optional_str_list(payload, "preference_tags"),
        tags=_optional_str_list(payload, "tags"),
        rider_classes=_optional_str_list(payload, "rider_classes"),
        ride_classes=_optional_str_list(payload, "ride_classes"),
        hero_photo=(
            _get_or_404(Image, _required_int(payload, "hero_photo_id"))
            if payload.get("hero_photo_id") is not None
            else None
        ),
    )
    return _group_payload(group), HTTPStatus.CREATED


@bp.post("/api/groups/<int:group_id>/memberships")
def create_group_membership_route(group_id: int) -> tuple[dict[str, object], int]:
    payload = _json_payload()
    group = _get_or_404(Group, group_id)
    user = _get_or_404(User, _required_int(payload, "user_id"))
    membership = ensure_group_membership(
        group,
        user,
        role_name=_optional_str(payload, "role_name"),
    )
    return _membership_payload(group, membership), HTTPStatus.CREATED


@bp.post("/api/groups/<int:group_id>/links")
def create_group_link_route(group_id: int) -> tuple[dict[str, object], int]:
    payload = _json_payload()
    group = _get_or_404(Group, group_id)
    link = add_group_link(
        group,
        name=_required_str(payload, "name"),
        url=_required_str(payload, "url"),
        link_type=_required_str({"type": payload.get("type", "website")}, "type"),
        tags=_optional_str_list(payload, "tags"),
    )
    return _group_link_payload(group, link), HTTPStatus.CREATED


@bp.post("/api/groups/<int:group_id>/dues")
def create_group_dues_route(group_id: int) -> tuple[dict[str, object], int]:
    payload = _json_payload()
    group = _get_or_404(Group, group_id)
    dues = add_group_dues(
        group,
        name=_required_str(payload, "name"),
        fee=_required_float(payload, "fee"),
        duration=_required_int(payload, "duration"),
        description=_optional_str(payload, "description"),
        tags=_optional_str_list(payload, "tags"),
    )
    return _group_dues_payload(group, dues), HTTPStatus.CREATED


@bp.get("/api/groups/<int:group_id>/routes")
def list_group_routes_route(group_id: int) -> tuple[dict[str, object], int]:
    group = _get_or_404(Group, group_id)
    return {"items": [_route_payload(route) for route in group.routes]}, HTTPStatus.OK


@bp.post("/api/groups/<int:group_id>/routes")
def attach_group_route_route(group_id: int) -> tuple[dict[str, object], int]:
    payload = _json_payload()
    group = _get_or_404(Group, group_id)
    route = _get_or_404(Route, _required_int(payload, "route_id"))
    attach_route_to_group(group, route)
    return {
        "group_id": group.id,
        "route_ids": [linked_route.id for linked_route in group.routes],
    }, HTTPStatus.CREATED


@bp.post("/api/events")
def create_event_route() -> tuple[dict[str, object], int]:
    payload = _json_payload()
    owner = (
        _get_or_404(User, _required_int(payload, "owner_id"))
        if payload.get("owner_id") is not None
        else None
    )
    event = create_event(
        name=_required_str(payload, "name"),
        owner=owner,
        route=(
            _get_or_404(Route, _required_int(payload, "route_id"))
            if payload.get("route_id") is not None
            else None
        ),
        activity=(
            _get_or_404(Activity, _required_int(payload, "activity_id"))
            if payload.get("activity_id") is not None
            else None
        ),
        private=_optional_bool(payload, "private", default=False),
        description=_optional_str(payload, "description"),
        url=_optional_str(payload, "url"),
        reg_url=_optional_str(payload, "reg_url"),
        photo_url=_optional_str(payload, "photo_url"),
        logo=_optional_str(payload, "logo"),
        profile_photo=_optional_str(payload, "profile_photo"),
        notes=_optional_str(payload, "notes"),
        tags=_optional_str_list(payload, "tags"),
        lat=_optional_float(payload, "lat"),
        lon=_optional_float(payload, "lon"),
        town=_optional_str(payload, "town"),
        state=_optional_str(payload, "state"),
        country=_optional_str(payload, "country"),
        latlng=_optional_str(payload, "latlng"),
        geoll=_optional_str(payload, "geoll"),
    )
    return _event_payload(event), HTTPStatus.CREATED


@bp.post("/api/events/<int:event_id>/calendar-links")
def attach_calendar_route(event_id: int) -> tuple[dict[str, object], int]:
    payload = _json_payload()
    event = _get_or_404(Event, event_id)
    calendar = _get_or_404(Calendar, _required_int(payload, "calendar_id"))
    attach_calendar(event, calendar)
    return {
        "event_id": event.id,
        "calendar_ids": [linked_calendar.id for linked_calendar in event.calendars],
    }, HTTPStatus.CREATED


@bp.post("/api/events/<int:event_id>/rsvps")
def set_rsvp_route(event_id: int) -> tuple[dict[str, object], int]:
    payload = _json_payload()
    event = _get_or_404(Event, event_id)
    user = _get_or_404(User, _required_int(payload, "user_id"))
    participation = set_rsvp(event, user, status_name=_required_str(payload, "status_name"))
    return _rsvp_payload(event, participation), HTTPStatus.CREATED


@bp.post("/api/events/<int:event_id>/fees")
def create_event_fee_route(event_id: int) -> tuple[dict[str, object], int]:
    payload = _json_payload()
    event = _get_or_404(Event, event_id)
    fee = add_event_fee(
        event,
        name=_required_str(payload, "name"),
        fee=_required_float(payload, "fee"),
        duration=_required_int(payload, "duration"),
        description=_optional_str(payload, "description"),
        tags=_optional_str_list(payload, "tags"),
    )
    return _event_fee_payload(event, fee), HTTPStatus.CREATED


@bp.get("/api/events/<int:event_id>/images")
def list_event_images_route(event_id: int) -> tuple[dict[str, object], int]:
    event = _get_or_404(Event, event_id)
    return {"items": [_image_payload(image) for image in event.images]}, HTTPStatus.OK


@bp.post("/api/events/<int:event_id>/images")
def attach_event_image_route(event_id: int) -> tuple[dict[str, object], int]:
    payload = _json_payload()
    event = _get_or_404(Event, event_id)
    image = _get_or_404(Image, _required_int(payload, "image_id"))
    attach_image_to_event(event, image)
    return {
        "event_id": event.id,
        "image_ids": [linked_image.id for linked_image in event.images],
    }, HTTPStatus.CREATED


@bp.get("/api/points-of-interest")
def list_points_of_interest_route() -> tuple[dict[str, object], int]:
    owner = None
    owner_id = request.args.get("owner_id", type=int)
    if owner_id is not None:
        owner = _get_or_404(User, owner_id)
    points = list_points_of_interest(owner=owner)
    return {"items": [_point_of_interest_payload(point) for point in points]}, HTTPStatus.OK


@bp.get("/api/points-of-interest/<int:point_id>/images")
def list_point_of_interest_images_route(point_id: int) -> tuple[dict[str, object], int]:
    point = _get_or_404(PointOfInterest, point_id)
    return {"items": [_image_payload(image) for image in point.images]}, HTTPStatus.OK


@bp.post("/api/points-of-interest/<int:point_id>/images")
def attach_point_of_interest_image_route(point_id: int) -> tuple[dict[str, object], int]:
    payload = _json_payload()
    point = _get_or_404(PointOfInterest, point_id)
    image = _get_or_404(Image, _required_int(payload, "image_id"))
    attach_image_to_poi(point, image)
    return {
        "point_id": point.id,
        "image_ids": [linked_image.id for linked_image in point.images],
    }, HTTPStatus.CREATED


@bp.post("/api/points-of-interest")
def create_point_of_interest_route() -> tuple[dict[str, object], int]:
    payload = _json_payload()
    owner = (
        _get_or_404(User, _required_int(payload, "owner_id"))
        if payload.get("owner_id") is not None
        else None
    )
    point = create_point_of_interest(
        owner=owner,
        name=_required_str(payload, "name"),
        poi_type=_optional_str(payload, "type"),
        subtype=_optional_str(payload, "subtype"),
        lat=_optional_float(payload, "lat"),
        lon=_optional_float(payload, "lon"),
        geoll=_optional_str(payload, "geoll"),
        url=_optional_str(payload, "url"),
        description=_optional_str(payload, "description"),
        tags=_optional_str_list(payload, "tags"),
        icon=_optional_str(payload, "icon"),
    )
    return _point_of_interest_payload(point), HTTPStatus.CREATED


@bp.get("/api/routes")
def list_routes_route() -> tuple[dict[str, object], int]:
    creator = None
    creator_id = request.args.get("creator_id", type=int)
    if creator_id is not None:
        creator = _get_or_404(User, creator_id)
    routes = list_routes(creator=creator)
    return {"items": [_route_payload(route) for route in routes]}, HTTPStatus.OK


@bp.post("/api/routes")
def create_route_route() -> tuple[dict[str, object], int]:
    payload = _json_payload()
    creator = (
        _get_or_404(User, _required_int(payload, "creator_id"))
        if payload.get("creator_id") is not None
        else None
    )
    route = create_route(
        creator=creator,
        name=_required_str(payload, "name"),
        desc=_optional_str(payload, "desc"),
        private=_optional_nullable_bool(payload, "private"),
        duration=_optional_float(payload, "duration"),
        length=_optional_float(payload, "length"),
        elevation_gain=_optional_float(payload, "elevation_gain"),
        tags=_optional_str_list(payload, "tags"),
        elevation_array=_optional_float_list(payload, "elevation_array"),
        route_type=_optional_str(payload, "type"),
        subtype=_optional_str(payload, "subtype"),
        src=_optional_str(payload, "src"),
        src_id=_optional_str(payload, "src_id"),
        start_latitude=_optional_float(payload, "start_latitude"),
        start_longitude=_optional_float(payload, "start_longitude"),
        end_latitude=_optional_float(payload, "end_latitude"),
        end_longitude=_optional_float(payload, "end_longitude"),
        summary_polyline=_optional_str(payload, "summary_polyline"),
        full_track=_optional_str(payload, "full_track"),
        city=_optional_str(payload, "city"),
        state=_optional_str(payload, "state"),
        country=_optional_str(payload, "country"),
        address=_optional_str(payload, "address"),
        map_thumbnail=_optional_str(payload, "map_thumbnail"),
    )
    return _route_payload(route), HTTPStatus.CREATED


@bp.get("/api/routes/<int:route_id>/links")
def list_route_links_route(route_id: int) -> tuple[dict[str, object], int]:
    route = _get_or_404(Route, route_id)
    return {"items": [_route_link_payload(route, link) for link in route.links]}, HTTPStatus.OK


@bp.post("/api/routes/<int:route_id>/links")
def create_route_link_route(route_id: int) -> tuple[dict[str, object], int]:
    payload = _json_payload()
    route = _get_or_404(Route, route_id)
    link = add_route_link(
        route,
        name=_required_str(payload, "name"),
        url=_required_str(payload, "url"),
        link_type=_required_str({"type": payload.get("type", "website")}, "type"),
        tags=_optional_str_list(payload, "tags"),
    )
    return _route_link_payload(route, link), HTTPStatus.CREATED


@bp.post("/api/routes/<int:route_id>/segments")
def attach_segment_to_route_route(route_id: int) -> tuple[dict[str, object], int]:
    payload = _json_payload()
    route = _get_or_404(Route, route_id)
    segment = _get_or_404(Segment, _required_int(payload, "segment_id"))
    attach_segment_to_route(route, segment)
    return {
        "route_id": route.id,
        "segment_ids": [linked_segment.id for linked_segment in route.segments],
    }, HTTPStatus.CREATED


@bp.get("/api/segments")
def list_segments_route() -> tuple[dict[str, object], int]:
    segments = list_segments()
    return {"items": [_segment_payload(segment) for segment in segments]}, HTTPStatus.OK


@bp.post("/api/segments")
def create_segment_route() -> tuple[dict[str, object], int]:
    payload = _json_payload()
    segment = create_segment(
        name=_required_str(payload, "name"),
        desc=_optional_str(payload, "desc"),
        duration=_optional_float(payload, "duration"),
        length=_optional_float(payload, "length"),
        elevation_gain=_optional_float(payload, "elevation_gain"),
        elevation_array=_optional_float_list(payload, "elevation_array"),
        elevation_loss=_optional_float(payload, "elevation_loss"),
        elev_high=_optional_float(payload, "elev_high"),
        elev_low=_optional_float(payload, "elev_low"),
        rating=_optional_float(payload, "rating"),
        grade=_optional_float(payload, "grade"),
        segment_type=_optional_str(payload, "type"),
        subtype=_optional_str(payload, "subtype"),
        tags=_optional_str_list(payload, "tags"),
        src=_optional_str(payload, "src"),
        src_id=_optional_str(payload, "src_id"),
        src_url=_optional_str(payload, "src_url"),
        start_latitude=_optional_float(payload, "start_latitude"),
        start_longitude=_optional_float(payload, "start_longitude"),
        end_latitude=_optional_float(payload, "end_latitude"),
        end_longitude=_optional_float(payload, "end_longitude"),
        summary_polyline=_optional_str(payload, "summary_polyline"),
        full_track=_optional_str(payload, "full_track"),
        track_hash=_optional_str(payload, "track_hash"),
        track_maxspeed=_optional_float(payload, "track_maxspeed"),
    )
    return _segment_payload(segment), HTTPStatus.CREATED


@bp.get("/api/activities")
def list_activities_route() -> tuple[dict[str, object], int]:
    athlete = None
    route = None
    athlete_id = request.args.get("athlete_id", type=int)
    route_id = request.args.get("route_id", type=int)
    if athlete_id is not None:
        athlete = _get_or_404(User, athlete_id)
    if route_id is not None:
        route = _get_or_404(Route, route_id)
    activities = list_activities(athlete=athlete, route=route)
    return {"items": [_activity_payload(activity) for activity in activities]}, HTTPStatus.OK


@bp.post("/api/activities")
def create_activity_route() -> tuple[dict[str, object], int]:
    payload = _json_payload()
    athlete = (
        _get_or_404(User, _required_int(payload, "athlete_id"))
        if payload.get("athlete_id") is not None
        else None
    )
    route = (
        _get_or_404(Route, _required_int(payload, "route_id"))
        if payload.get("route_id") is not None
        else None
    )
    activity = create_activity(
        athlete=athlete,
        route=route,
        name=_required_str(payload, "name"),
        desc=_optional_str(payload, "desc"),
        private=_optional_nullable_bool(payload, "private"),
        photo_url=_optional_str(payload, "photo_url"),
        tags=_optional_str_list(payload, "tags"),
        duration=_optional_float(payload, "duration"),
        length=_optional_float(payload, "length"),
        elevation_gain=_optional_float(payload, "elevation_gain"),
        average_speed=_optional_float(payload, "average_speed"),
        max_speed=_optional_float(payload, "max_speed"),
        moving_time=_optional_float(payload, "moving_time"),
        total_elevation_gain=_optional_float(payload, "total_elevation_gain"),
        elev_high=_optional_float(payload, "elev_high"),
        elev_low=_optional_float(payload, "elev_low"),
        activity_type=_optional_str(payload, "type"),
        subtype=_optional_str(payload, "subtype"),
        src=_optional_str(payload, "src"),
        src_id=_optional_str(payload, "src_id"),
        start_latitude=_optional_float(payload, "start_latitude"),
        start_longitude=_optional_float(payload, "start_longitude"),
        end_latitude=_optional_float(payload, "end_latitude"),
        end_longitude=_optional_float(payload, "end_longitude"),
        summary_polyline=_optional_str(payload, "summary_polyline"),
        full_track=_optional_str(payload, "full_track"),
    )
    return _activity_payload(activity), HTTPStatus.CREATED


@bp.get("/api/images")
def list_images_route() -> tuple[dict[str, object], int]:
    photographer = None
    group = None
    segment = None
    activity = None
    photographer_id = request.args.get("photographer_id", type=int)
    group_id = request.args.get("group_id", type=int)
    segment_id = request.args.get("segment_id", type=int)
    activity_id = request.args.get("activity_id", type=int)
    if photographer_id is not None:
        photographer = _get_or_404(User, photographer_id)
    if group_id is not None:
        group = _get_or_404(Group, group_id)
    if segment_id is not None:
        segment = _get_or_404(Segment, segment_id)
    if activity_id is not None:
        activity = _get_or_404(Activity, activity_id)
    images = list_images(
        photographer=photographer,
        group=group,
        segment=segment,
        activity=activity,
    )
    return {"items": [_image_payload(image) for image in images]}, HTTPStatus.OK


@bp.post("/api/images")
def create_image_route() -> tuple[dict[str, object], int]:
    payload = _json_payload()
    image = create_image(
        photographer=(
            _get_or_404(User, _required_int(payload, "photographer_id"))
            if payload.get("photographer_id") is not None
            else None
        ),
        group=(
            _get_or_404(Group, _required_int(payload, "group_id"))
            if payload.get("group_id") is not None
            else None
        ),
        segment=(
            _get_or_404(Segment, _required_int(payload, "segment_id"))
            if payload.get("segment_id") is not None
            else None
        ),
        activity=(
            _get_or_404(Activity, _required_int(payload, "activity_id"))
            if payload.get("activity_id") is not None
            else None
        ),
        img_small=_optional_str(payload, "img_small"),
        img_medium=_optional_str(payload, "img_medium"),
        img_large=_optional_str(payload, "img_large"),
        img_thumb=_optional_str(payload, "img_thumb"),
        alt_txt=_optional_str(payload, "alt_txt"),
        title=_optional_str(payload, "title"),
        caption=_optional_str(payload, "caption"),
        latlng=_optional_str(payload, "latlng"),
        geoll=_optional_str(payload, "geoll"),
        tags=_optional_str_list(payload, "tags"),
        url=_optional_str(payload, "url"),
    )
    return _image_payload(image), HTTPStatus.CREATED


def _json_payload() -> dict[str, Any]:
    return cast(dict[str, Any], request.get_json(force=True, silent=False))


def _get_or_404(model: type[ModelT], record_id: int) -> ModelT:
    record = db.session.get(model, record_id)
    if record is None:
        abort(HTTPStatus.NOT_FOUND)
    return record


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        abort(HTTPStatus.BAD_REQUEST)
    return value


def _optional_str(payload: dict[str, Any], key: str, *, default: str | None = None) -> str | None:
    value = payload.get(key, default)
    if value is None:
        return None
    if not isinstance(value, str):
        abort(HTTPStatus.BAD_REQUEST)
    return value


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        abort(HTTPStatus.BAD_REQUEST)
    return value


def _required_float(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        abort(HTTPStatus.BAD_REQUEST)
    return float(value)


def _optional_float(payload: dict[str, Any], key: str) -> float | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        abort(HTTPStatus.BAD_REQUEST)
    return float(value)


def _optional_bool(payload: dict[str, Any], key: str, *, default: bool) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        abort(HTTPStatus.BAD_REQUEST)
    return value


def _optional_str_list(payload: dict[str, Any], key: str) -> list[str] | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        abort(HTTPStatus.BAD_REQUEST)
    return value


def _optional_float_list(payload: dict[str, Any], key: str) -> list[float] | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, list):
        abort(HTTPStatus.BAD_REQUEST)
    converted: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int | float):
            abort(HTTPStatus.BAD_REQUEST)
        converted.append(float(item))
    return converted


def _optional_nullable_bool(payload: dict[str, Any], key: str) -> bool | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        abort(HTTPStatus.BAD_REQUEST)
    return value


def _group_payload(group: Group) -> dict[str, object]:
    return {
        "id": group.id,
        "name": group.name,
        "shortname": group.shortname,
        "invite_only": group.invite_only,
        "private": group.private,
        "home_town": group.home_town,
        "home_state": group.home_state,
        "home_country": group.home_country,
        "home_latlng": group.home_latlng,
        "home_add": group.home_add,
        "full_address": group.full_address,
        "geoll": group.geoll,
        "preference_tags": group.preference_tags,
        "tags": group.tags,
        "rider_classes": group.rider_classes,
        "ride_classes": group.ride_classes,
        "hero_photo_id": group.hero_photo_id,
    }


def _membership_payload(group: Group, membership: Membership) -> dict[str, object]:
    return {
        "group_id": group.id,
        "membership_id": membership.id,
        "user_id": membership.user_id,
        "role_name": membership.role.name,
    }


def _group_link_payload(group: Group, link: GroupExternalUrl) -> dict[str, object]:
    return {
        "group_id": group.id,
        "link_id": link.id,
        "name": link.name,
        "type": link.type,
        "tags": link.tags,
        "url": link.url,
    }


def _group_dues_payload(group: Group, dues: GroupDues) -> dict[str, object]:
    return {
        "group_id": group.id,
        "dues_id": dues.id,
        "name": dues.name,
        "fee": dues.fee,
        "duration": dues.duration,
        "tags": dues.tags,
    }


def _route_link_payload(route: Route, link: GroupExternalUrl) -> dict[str, object]:
    return {
        "route_id": route.id,
        "link_id": link.id,
        "name": link.name,
        "type": link.type,
        "tags": link.tags,
        "url": link.url,
    }


def _event_payload(event: Event) -> dict[str, object]:
    return {
        "id": event.id,
        "name": event.name,
        "owner_id": event.owner_id,
        "route_id": event.route_id,
        "activity_id": event.activity_id,
        "private": event.private,
        "description": event.description,
        "url": event.url,
        "reg_url": event.reg_url,
        "photo_url": event.photo_url,
        "logo": event.logo,
        "profile_photo": event.profile_photo,
        "notes": event.notes,
        "tags": event.tags,
        "lat": event.lat,
        "lon": event.lon,
        "town": event.town,
        "state": event.state,
        "country": event.country,
        "latlng": event.latlng,
        "geoll": event.geoll,
    }


def _rsvp_payload(event: Event, participation: EventInvitation) -> dict[str, object]:
    return {
        "event_id": event.id,
        "participation_id": participation.id,
        "user_id": participation.user_id,
        "status_name": participation.status.name,
    }


def _event_fee_payload(event: Event, fee: EventFee) -> dict[str, object]:
    return {
        "event_id": event.id,
        "fee_id": fee.id,
        "name": fee.name,
        "fee": fee.fee,
        "duration": fee.duration,
        "tags": fee.tags,
    }


def _point_of_interest_payload(point: PointOfInterest) -> dict[str, object]:
    return {
        "id": point.id,
        "owner_id": point.owner_id,
        "name": point.name,
        "type": point.type,
        "subtype": point.subtype,
        "lat": point.lat,
        "lon": point.lon,
        "geoll": point.geoll,
        "url": point.url,
        "description": point.description,
        "tags": point.tags,
        "icon": point.icon,
    }


def _route_payload(route: Route) -> dict[str, object]:
    return {
        "id": route.id,
        "creator_id": route.creator_id,
        "name": route.name,
        "desc": route.desc,
        "private": route.private,
        "duration": route.duration,
        "length": route.length,
        "elevation_gain": route.elevation_gain,
        "tags": route.tags,
        "elevation_array": route.elevation_array,
        "type": route.type,
        "subtype": route.subtype,
        "src": route.src,
        "src_id": route.src_id,
        "start_latitude": route.start_latitude,
        "start_longitude": route.start_longitude,
        "end_latitude": route.end_latitude,
        "end_longitude": route.end_longitude,
        "summary_polyline": route.summary_polyline,
        "full_track": route.full_track,
        "city": route.city,
        "state": route.state,
        "country": route.country,
        "address": route.address,
        "map_thumbnail": route.map_thumbnail,
    }


def _segment_payload(segment: Segment) -> dict[str, object]:
    return {
        "id": segment.id,
        "name": segment.name,
        "desc": segment.desc,
        "duration": segment.duration,
        "length": segment.length,
        "elevation_gain": segment.elevation_gain,
        "elevation_array": segment.elevation_array,
        "elevation_loss": segment.elevation_loss,
        "elev_high": segment.elev_high,
        "elev_low": segment.elev_low,
        "rating": segment.rating,
        "grade": segment.grade,
        "type": segment.type,
        "subtype": segment.subtype,
        "tags": segment.tags,
        "src": segment.src,
        "src_id": segment.src_id,
        "src_url": segment.src_url,
        "start_latitude": segment.start_latitude,
        "start_longitude": segment.start_longitude,
        "end_latitude": segment.end_latitude,
        "end_longitude": segment.end_longitude,
        "summary_polyline": segment.summary_polyline,
        "full_track": segment.full_track,
        "track_hash": segment.track_hash,
        "track_maxspeed": segment.track_maxspeed,
    }


def _activity_payload(activity: Activity) -> dict[str, object]:
    return {
        "id": activity.id,
        "athlete_id": activity.athlete_id,
        "route_id": activity.route_id,
        "name": activity.name,
        "desc": activity.desc,
        "private": activity.private,
        "photo_url": activity.photo_url,
        "tags": activity.tags,
        "duration": activity.duration,
        "length": activity.length,
        "elevation_gain": activity.elevation_gain,
        "average_speed": activity.average_speed,
        "max_speed": activity.max_speed,
        "moving_time": activity.moving_time,
        "total_elevation_gain": activity.total_elevation_gain,
        "elev_high": activity.elev_high,
        "elev_low": activity.elev_low,
        "type": activity.type,
        "subtype": activity.subtype,
        "src": activity.src,
        "src_id": activity.src_id,
        "start_latitude": activity.start_latitude,
        "start_longitude": activity.start_longitude,
        "end_latitude": activity.end_latitude,
        "end_longitude": activity.end_longitude,
        "summary_polyline": activity.summary_polyline,
        "full_track": activity.full_track,
    }


def _image_payload(image: Image) -> dict[str, object]:
    return {
        "id": image.id,
        "photographer_id": image.photographer_id,
        "group_id": image.group_id,
        "segment_id": image.segment_id,
        "activity_id": image.activity_id,
        "img_small": image.img_small,
        "img_medium": image.img_medium,
        "img_large": image.img_large,
        "img_thumb": image.img_thumb,
        "alt_txt": image.alt_txt,
        "title": image.title,
        "caption": image.caption,
        "latlng": image.latlng,
        "geoll": image.geoll,
        "tags": image.tags,
        "url": image.url,
    }


def _search_document_payload(document: SearchDocument) -> dict[str, object]:
    return {
        "entity_type": document.entity_type,
        "entity_id": document.entity_id,
        "title": document.title,
        "subtitle": document.subtitle,
        "location": document.location,
        "tags": document.tags,
    }


def _admin_search_result_item(document: SearchDocument) -> dict[str, object]:
    return {
        **_search_document_payload(document),
        "detail_url": _admin_detail_url(document.entity_type, document.entity_id),
    }


def _public_search_result_item(document: SearchDocument) -> dict[str, object]:
    detail_url = None
    if current_user.is_authenticated and getattr(current_user, "site_admin", False):
        detail_url = _admin_detail_url(document.entity_type, document.entity_id)

    return {
        **_search_document_payload(document),
        "detail_url": detail_url,
    }


def _dashboard_group_item(group: Group) -> dict[str, object]:
    return {
        "detail_url": url_for("core.admin_group_detail_route", group_id=group.id),
        "id": group.id,
        "location": _join_location(group.home_town, group.home_state, group.home_country),
        "subtitle": group.shortname or group.primary_activity or group.type,
        "title": group.name or "Group",
    }


def _dashboard_user_item(user: User) -> dict[str, object]:
    return {
        "detail_url": url_for("core.admin_user_detail_route", user_id=user.id),
        "id": user.id,
        "location": _join_location(user.home_town, user.home_state, user.home_country),
        "subtitle": user.email,
        "title": user.display_name,
    }


def _dashboard_image_item(image: Image) -> dict[str, object]:
    return {
        "detail_url": url_for("core.admin_image_detail_route", image_id=image.id),
        "id": image.id,
        "location": image.latlng,
        "subtitle": image.img_medium or image.url,
        "title": image.title or "Image",
    }


def _dashboard_link_item(link: GroupExternalUrl) -> dict[str, object]:
    owner = (
        f"Group {link.group_id}"
        if link.group_id is not None
        else f"Route {link.route_id}"
        if link.route_id is not None
        else None
    )
    return {
        "detail_url": url_for("core.admin_link_detail_route", link_id=link.id),
        "id": link.id,
        "location": None,
        "subtitle": owner or link.url,
        "title": link.name or "Link",
    }


def _dashboard_dues_item(dues: GroupDues) -> dict[str, object]:
    return {
        "detail_url": url_for("core.admin_dues_detail_route", dues_id=dues.id),
        "id": dues.id,
        "location": None,
        "subtitle": f"Group {dues.group_id}" if dues.group_id is not None else None,
        "title": dues.name or "Dues",
    }


def _dashboard_fee_item(fee: EventFee) -> dict[str, object]:
    return {
        "detail_url": url_for("core.admin_fee_detail_route", fee_id=fee.id),
        "id": fee.id,
        "location": None,
        "subtitle": f"Event {fee.event_id}" if fee.event_id is not None else None,
        "title": fee.name or "Fee",
    }


def _dashboard_route_item(route: Route) -> dict[str, object]:
    return {
        "detail_url": url_for("core.admin_route_detail_route", route_id=route.id),
        "id": route.id,
        "location": _join_location(route.city, route.state, route.country),
        "subtitle": route.subtype or route.type,
        "title": route.name or "Route",
    }


def _dashboard_segment_item(segment: Segment) -> dict[str, object]:
    return {
        "detail_url": url_for("core.admin_segment_detail_route", segment_id=segment.id),
        "id": segment.id,
        "location": None,
        "subtitle": segment.subtype or segment.type,
        "title": segment.name or "Segment",
    }


def _dashboard_event_item(event: Event) -> dict[str, object]:
    return {
        "detail_url": url_for("core.admin_event_detail_route", event_id=event.id),
        "id": event.id,
        "location": _join_location(event.town, event.state, event.country),
        "subtitle": event.subtype or event.type or event.primary_activity,
        "title": event.name or "Event",
    }


def _dashboard_calendar_item(calendar: Calendar) -> dict[str, object]:
    return {
        "detail_url": url_for("core.admin_calendar_detail_route", calendar_id=calendar.id),
        "id": calendar.id,
        "location": calendar.group.name if calendar.group is not None else None,
        "subtitle": calendar.subtype or calendar.type or calendar.primary_activity,
        "title": calendar.name or "Calendar",
    }


def _dashboard_poi_item(point: PointOfInterest) -> dict[str, object]:
    return {
        "detail_url": url_for("core.admin_point_of_interest_detail_route", point_id=point.id),
        "id": point.id,
        "location": None,
        "subtitle": point.subtype or point.type,
        "title": point.name or "Point of Interest",
    }


def _dashboard_activity_item(activity: Activity) -> dict[str, object]:
    return {
        "detail_url": url_for("core.admin_activity_detail_route", activity_id=activity.id),
        "id": activity.id,
        "location": None,
        "subtitle": activity.subtype or activity.type,
        "title": activity.name or "Activity",
    }


def _recent_records(model: type[ModelT], *, limit: int = 5) -> list[ModelT]:
    order_column = cast(Any, model).id.desc()
    return list(db.session.scalars(select(model).order_by(order_column).limit(limit)))


def _count_records(model: type[ModelT]) -> int:
    return db.session.scalar(select(func.count()).select_from(model)) or 0


def _public_browser_limit() -> int:
    requested = request.args.get("limit", default=PUBLIC_BROWSER_LIMIT, type=int)
    return min(max(requested, 1), PUBLIC_BROWSER_LIMIT)


def _public_browser_offset() -> int:
    requested = request.args.get("offset", default=0, type=int)
    return max(requested, 0)


def _recent_activity_links(
    *, exclude: tuple[str, int] | None = None, limit: int = 6
) -> list[dict[str, object]]:
    statement = select(SearchDocument).order_by(SearchDocument.updated_at.desc()).limit(limit + 1)
    documents = list(db.session.scalars(statement))
    links: list[dict[str, object]] = []
    for document in documents:
        identity = (document.entity_type, document.entity_id)
        if exclude is not None and identity == exclude:
            continue
        detail_url = _admin_detail_url(document.entity_type, document.entity_id)
        if detail_url is None:
            continue
        links.append(
            {
                "detail_url": detail_url,
                "entity_type_label": document.entity_type.replace("_", " ").title(),
                "title": document.title or "(untitled)",
            }
        )
        if len(links) >= limit:
            break
    return links


def _recent_user_links(
    *,
    exclude_user_id: int | None = None,
    limit: int = 6,
) -> list[dict[str, object]]:
    statement = select(User).order_by(User.update_date.desc()).limit(limit + 1)
    users = list(db.session.scalars(statement))
    links: list[dict[str, object]] = []
    for user in users:
        if exclude_user_id is not None and user.id == exclude_user_id:
            continue
        links.append(
            {
                "detail_url": url_for("core.admin_user_detail_route", user_id=user.id),
                "entity_type_label": "User",
                "title": user.display_name,
            }
        )
        if len(links) >= limit:
            break
    return links


def _recent_image_links(
    *,
    exclude_image_id: int | None = None,
    limit: int = 6,
) -> list[dict[str, object]]:
    images = list(db.session.scalars(select(Image).order_by(Image.id.desc()).limit(limit + 1)))
    return _recent_record_links(
        images,
        exclude_id=exclude_image_id,
        label="Image",
        endpoint="core.admin_image_detail_route",
        key="image_id",
        title_getter=lambda image: image.title or "Image",
    )


def _recent_link_links(
    *,
    exclude_link_id: int | None = None,
    limit: int = 6,
) -> list[dict[str, object]]:
    links = list(
        db.session.scalars(
            select(GroupExternalUrl).order_by(GroupExternalUrl.id.desc()).limit(limit + 1)
        )
    )
    return _recent_record_links(
        links,
        exclude_id=exclude_link_id,
        label="Link",
        endpoint="core.admin_link_detail_route",
        key="link_id",
        title_getter=lambda link: link.name or "Link",
    )


def _recent_dues_links(
    *,
    exclude_dues_id: int | None = None,
    limit: int = 6,
) -> list[dict[str, object]]:
    dues_entries = list(
        db.session.scalars(select(GroupDues).order_by(GroupDues.id.desc()).limit(limit + 1))
    )
    return _recent_record_links(
        dues_entries,
        exclude_id=exclude_dues_id,
        label="Dues",
        endpoint="core.admin_dues_detail_route",
        key="dues_id",
        title_getter=lambda dues: dues.name or "Dues",
    )


def _recent_fee_links(
    *,
    exclude_fee_id: int | None = None,
    limit: int = 6,
) -> list[dict[str, object]]:
    fees = list(db.session.scalars(select(EventFee).order_by(EventFee.id.desc()).limit(limit + 1)))
    return _recent_record_links(
        fees,
        exclude_id=exclude_fee_id,
        label="Fee",
        endpoint="core.admin_fee_detail_route",
        key="fee_id",
        title_getter=lambda fee: fee.name or "Fee",
    )


def _recent_record_links(
    records: list[ModelT],
    *,
    exclude_id: int | None,
    label: str,
    endpoint: str,
    key: str,
    title_getter: Any,
) -> list[dict[str, object]]:
    links: list[dict[str, object]] = []
    for record in records:
        record_id = cast(int, getattr(record, "id"))
        if exclude_id is not None and record_id == exclude_id:
            continue
        route_kwargs = cast(dict[str, Any], {key: record_id})
        links.append(
            {
                "detail_url": url_for(endpoint, **route_kwargs),
                "entity_type_label": label,
                "title": title_getter(record),
            }
        )
    return links


def _coordinate_pair(latitude: float | None, longitude: float | None) -> str | None:
    if latitude is None or longitude is None:
        return None
    return f"{latitude:.5f}, {longitude:.5f}"


def _current_unit_system() -> str:
    if current_user.is_authenticated:
        units = getattr(current_user, "units", None)
        if units in {"metric", "imperial"}:
            return cast(str, units)
    return "metric"


def _browser_page_payload(
    *,
    collection_key: str,
    collection_label: str,
    api_url: str,
    bundle: dict[str, object],
    filter_options: dict[str, object],
) -> dict[str, object]:
    items = cast(list[dict[str, object]], bundle["items"])
    focus = _browser_focus_point(items)
    bounds = _browser_world_bounds(items, focus=focus)
    return {
        "apiUrl": api_url,
        "collectionKey": collection_key,
        "collectionLabel": collection_label,
        "bounds": bounds,
        "filterOptions": filter_options,
        "focus": focus,
        "items": items,
        "limit": bundle["limit"],
        "offset": bundle["offset"],
        "totalMatching": bundle["total_matching"],
    }


def _browser_focus_point(items: Sequence[dict[str, object]]) -> dict[str, float] | None:
    if current_user.is_authenticated:
        coordinates = point_coordinates(getattr(current_user, "geoll", None))
        if coordinates is not None:
            longitude, latitude = coordinates
            return {"lat": latitude, "lng": longitude}
    return _browser_item_center(items[0]) if items else None


def _browser_item_center(item: dict[str, object]) -> dict[str, float] | None:
    center = cast(dict[str, float] | None, item.get("center"))
    return center if center is not None else None


def _browser_world_bounds(
    items: Sequence[dict[str, object]],
    *,
    focus: dict[str, float] | None,
) -> dict[str, float]:
    latitudes: list[float] = []
    longitudes: list[float] = []
    for item in items:
        center = _browser_item_center(item)
        if center is None:
            continue
        latitudes.append(center["lat"])
        longitudes.append(center["lng"])

    if focus is not None:
        latitudes.append(focus["lat"])
        longitudes.append(focus["lng"])

    if not latitudes or not longitudes:
        return {"maxLat": 52.0, "maxLng": -66.0, "minLat": 20.0, "minLng": -128.0}

    min_lat = min(latitudes)
    max_lat = max(latitudes)
    min_lng = min(longitudes)
    max_lng = max(longitudes)
    lat_pad = max((max_lat - min_lat) * 0.18, 0.35)
    lng_pad = max((max_lng - min_lng) * 0.18, 0.35)
    return {
        "maxLat": max_lat + lat_pad,
        "maxLng": max_lng + lng_pad,
        "minLat": min_lat - lat_pad,
        "minLng": min_lng - lng_pad,
    }


def _browser_query_text() -> str:
    return request.args.get("q", default="", type=str).strip()


def _browser_query_sort() -> str:
    requested = request.args.get("sort", default="closest", type=str).strip().lower()
    return requested if requested in {"closest", "duration", "elevation", "length"} else "closest"


def _browser_query_bool(name: str) -> bool:
    return request.args.get(name, default="", type=str).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _browser_query_bbox() -> dict[str, float] | None:
    min_lat = request.args.get("min_lat", type=float)
    max_lat = request.args.get("max_lat", type=float)
    min_lng = request.args.get("min_lng", type=float)
    max_lng = request.args.get("max_lng", type=float)
    if None in {min_lat, max_lat, min_lng, max_lng}:
        return None
    return {
        "min_lat": cast(float, min_lat),
        "max_lat": cast(float, max_lat),
        "min_lng": cast(float, min_lng),
        "max_lng": cast(float, max_lng),
    }


def _browser_focus_query_point() -> dict[str, float] | None:
    focus_lat = request.args.get("focus_lat", type=float)
    focus_lng = request.args.get("focus_lng", type=float)
    if focus_lat is None or focus_lng is None:
        return None
    return {"lat": focus_lat, "lng": focus_lng}


def _browser_center_latitude(start_latitude: Any, end_latitude: Any) -> Any:
    return func.coalesce((start_latitude + end_latitude) / 2, start_latitude, end_latitude)


def _browser_center_longitude(start_longitude: Any, end_longitude: Any) -> Any:
    return func.coalesce(
        (start_longitude + end_longitude) / 2,
        start_longitude,
        end_longitude,
    )


def _browser_text_clause(columns: Sequence[Any], query: str) -> Any | None:
    normalized = query.strip().lower()
    if not normalized:
        return None
    pattern = f"%{normalized}%"
    return or_(*[func.lower(func.coalesce(column, "")).like(pattern) for column in columns])


def _browser_favorite_clause(column: Any) -> Any:
    return or_(
        func.lower(sql_cast(column, String)).like("%favorite%"),
        func.lower(sql_cast(column, String)).like("%featured%"),
        func.lower(sql_cast(column, String)).like("%saved%"),
        func.lower(sql_cast(column, String)).like("%starred%"),
        func.lower(sql_cast(column, String)).like("%classic%"),
    )


def _browser_count_item(
    label: str,
    value: int | None,
    *,
    hide_zero: bool = False,
) -> dict[str, object] | None:
    if value is None:
        return None
    if hide_zero and value == 0:
        return None
    return {"label": label, "value": value}


def _browser_sort_expressions(
    *,
    model_id: Any,
    sort_key: str,
    distance_expression: Any | None,
    duration_column: Any,
    elevation_column: Any,
    length_column: Any,
) -> list[Any]:
    if sort_key == "closest" and distance_expression is not None:
        return [distance_expression.is_(None), distance_expression.asc(), model_id.desc()]
    if sort_key == "duration":
        return [duration_column.is_(None), duration_column.asc(), model_id.desc()]
    if sort_key == "elevation":
        return [elevation_column.is_(None), elevation_column.asc(), model_id.desc()]
    if sort_key == "length":
        return [length_column.is_(None), length_column.asc(), model_id.desc()]
    return [model_id.desc()]


def _route_browser_bundle() -> dict[str, object]:
    limit = _public_browser_limit()
    offset = _public_browser_offset()
    route_ids, total_matching = _route_browser_ids(limit=limit, offset=offset)
    routes = _route_browser_records(route_ids)
    event_counts = _route_event_count_map(route_ids)
    items = [
        _route_browser_item(route, event_count=event_counts.get(route.id, 0)) for route in routes
    ]
    return {
        "items": items,
        "limit": limit,
        "offset": offset,
        "total_matching": total_matching,
    }


def _segment_browser_bundle() -> dict[str, object]:
    limit = _public_browser_limit()
    offset = _public_browser_offset()
    segment_ids, total_matching = _segment_browser_ids(limit=limit, offset=offset)
    segments = _segment_browser_records(segment_ids)
    items = [_segment_browser_item(segment) for segment in segments]
    return {
        "items": items,
        "limit": limit,
        "offset": offset,
        "total_matching": total_matching,
    }


def _route_browser_ids(*, limit: int, offset: int) -> tuple[list[int], int]:
    query = _browser_query_text()
    sort_key = _browser_query_sort()
    favorites_only = _browser_query_bool("favorites_only")
    eventful_only = _browser_query_bool("eventful_only")
    terrain = request.args.get("terrain", default="", type=str).strip()
    club_id = request.args.get("club_id", type=int)
    bbox = _browser_query_bbox()
    focus = _browser_focus_query_point() or _browser_focus_point([])

    center_latitude = _browser_center_latitude(Route.start_latitude, Route.end_latitude)
    center_longitude = _browser_center_longitude(Route.start_longitude, Route.end_longitude)
    statement = select(Route.id)

    text_clause = _browser_text_clause(
        [
            Route.name,
            Route.desc,
            Route.type,
            Route.subtype,
            Route.city,
            Route.state,
            Route.country,
            sql_cast(Route.tags, String),
        ],
        query,
    )
    if text_clause is not None:
        statement = statement.where(text_clause)

    if favorites_only:
        statement = statement.where(_browser_favorite_clause(Route.tags))

    if terrain:
        terrain_clause = _browser_text_clause(
            [Route.type, Route.subtype, sql_cast(Route.tags, String)],
            terrain,
        )
        if terrain_clause is not None:
            statement = statement.where(terrain_clause)

    if club_id is not None:
        statement = statement.join(group_routes, group_routes.c.route == Route.id).where(
            group_routes.c.group == club_id
        )

    if eventful_only:
        statement = statement.where(select(Event.id).where(Event.route_id == Route.id).exists())

    if bbox is not None:
        statement = statement.where(
            center_latitude >= bbox["min_lat"],
            center_latitude <= bbox["max_lat"],
            center_longitude >= bbox["min_lng"],
            center_longitude <= bbox["max_lng"],
        )

    total_matching = (
        db.session.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
        or 0
    )

    distance_expression = None
    if focus is not None:
        distance_expression = func.abs(center_latitude - focus["lat"]) + func.abs(
            center_longitude - focus["lng"]
        )

    route_ids = list(
        db.session.scalars(
            statement.order_by(
                *_browser_sort_expressions(
                    model_id=Route.id,
                    sort_key=sort_key,
                    distance_expression=distance_expression,
                    duration_column=Route.duration,
                    elevation_column=Route.elevation_gain,
                    length_column=Route.length,
                )
            )
            .offset(offset)
            .limit(limit)
        )
    )
    return route_ids, total_matching


def _segment_browser_ids(*, limit: int, offset: int) -> tuple[list[int], int]:
    query = _browser_query_text()
    sort_key = _browser_query_sort()
    favorites_only = _browser_query_bool("favorites_only")
    eventful_only = _browser_query_bool("eventful_only")
    terrain = request.args.get("terrain", default="", type=str).strip()
    club_id = request.args.get("club_id", type=int)
    bbox = _browser_query_bbox()
    focus = _browser_focus_query_point() or _browser_focus_point([])

    center_latitude = _browser_center_latitude(Segment.start_latitude, Segment.end_latitude)
    center_longitude = _browser_center_longitude(Segment.start_longitude, Segment.end_longitude)
    statement = select(Segment.id)

    text_clause = _browser_text_clause(
        [
            Segment.name,
            Segment.desc,
            Segment.type,
            Segment.subtype,
            sql_cast(Segment.tags, String),
        ],
        query,
    )
    if text_clause is not None:
        statement = statement.where(text_clause)

    if favorites_only:
        statement = statement.where(_browser_favorite_clause(Segment.tags))

    if terrain:
        terrain_clause = _browser_text_clause(
            [Segment.type, Segment.subtype, sql_cast(Segment.tags, String)],
            terrain,
        )
        if terrain_clause is not None:
            statement = statement.where(terrain_clause)

    if club_id is not None:
        statement = statement.where(
            select(route_segments.c.segments)
            .select_from(
                route_segments.join(group_routes, route_segments.c.routes == group_routes.c.route)
            )
            .where(
                route_segments.c.segments == Segment.id,
                group_routes.c.group == club_id,
            )
            .exists()
        )

    if eventful_only:
        statement = statement.where(
            select(route_segments.c.segments)
            .select_from(route_segments.join(Event, route_segments.c.routes == Event.route_id))
            .where(route_segments.c.segments == Segment.id)
            .exists()
        )

    if bbox is not None:
        statement = statement.where(
            center_latitude >= bbox["min_lat"],
            center_latitude <= bbox["max_lat"],
            center_longitude >= bbox["min_lng"],
            center_longitude <= bbox["max_lng"],
        )

    total_matching = (
        db.session.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
        or 0
    )

    distance_expression = None
    if focus is not None:
        distance_expression = func.abs(center_latitude - focus["lat"]) + func.abs(
            center_longitude - focus["lng"]
        )

    segment_ids = list(
        db.session.scalars(
            statement.order_by(
                *_browser_sort_expressions(
                    model_id=Segment.id,
                    sort_key=sort_key,
                    distance_expression=distance_expression,
                    duration_column=Segment.duration,
                    elevation_column=Segment.elevation_gain,
                    length_column=Segment.length,
                )
            )
            .offset(offset)
            .limit(limit)
        )
    )
    return segment_ids, total_matching


def _route_browser_records(route_ids: Sequence[int]) -> list[Route]:
    if not route_ids:
        return []
    statement = (
        select(Route)
        .options(
            load_only(
                Route.id,
                Route.name,
                Route.desc,
                Route.duration,
                Route.length,
                Route.elevation_gain,
                Route.tags,
                Route.type,
                Route.subtype,
                Route.rating,
                Route.grade,
                Route.start_latitude,
                Route.start_longitude,
                Route.end_latitude,
                Route.end_longitude,
                Route._summary_polyline,
                Route.city,
                Route.state,
                Route.country,
            ),
            selectinload(Route.groups).load_only(Group.id, Group.name),
            selectinload(Route.segments).load_only(Segment.id),
        )
        .where(Route.id.in_(route_ids))
    )
    records = list(db.session.scalars(statement))
    order = {route_id: index for index, route_id in enumerate(route_ids)}
    return sorted(records, key=lambda route: order.get(route.id, len(route_ids)))


def _segment_browser_records(segment_ids: Sequence[int]) -> list[Segment]:
    if not segment_ids:
        return []
    statement = (
        select(Segment)
        .options(
            load_only(
                Segment.id,
                Segment.name,
                Segment.desc,
                Segment.duration,
                Segment.length,
                Segment.elevation_gain,
                Segment.rating,
                Segment.grade,
                Segment.tags,
                Segment.type,
                Segment.subtype,
                Segment.start_latitude,
                Segment.start_longitude,
                Segment.end_latitude,
                Segment.end_longitude,
                Segment._summary_polyline,
            ),
            selectinload(Segment.routes).load_only(Route.id, Route.name),
            selectinload(Segment.images).load_only(Image.id),
        )
        .where(Segment.id.in_(segment_ids))
    )
    records = list(db.session.scalars(statement))
    order = {segment_id: index for index, segment_id in enumerate(segment_ids)}
    return sorted(records, key=lambda segment: order.get(segment.id, len(segment_ids)))


def _route_event_count_map(route_ids: Sequence[int]) -> dict[int, int]:
    if not route_ids:
        return {}
    rows = db.session.execute(
        select(Event.route_id, func.count(Event.id))
        .where(Event.route_id.in_(route_ids))
        .where(Event.route_id.is_not(None))
        .group_by(Event.route_id)
    )
    return {
        cast(int, route_id): cast(int, count) for route_id, count in rows if route_id is not None
    }


def _route_browser_filter_options() -> dict[str, object]:
    return {
        "clubs": _browser_club_filter_options(),
        "terrains": _route_terrain_filter_options(),
    }


def _segment_browser_filter_options() -> dict[str, object]:
    return {
        "clubs": _browser_club_filter_options(),
        "terrains": _segment_terrain_filter_options(),
    }


def _browser_club_filter_options(limit: int = 8) -> list[dict[str, object]]:
    rows = db.session.execute(
        select(Group.id, Group.name, func.count(group_routes.c.route))
        .join(group_routes, group_routes.c.group == Group.id)
        .group_by(Group.id, Group.name)
        .order_by(func.count(group_routes.c.route).desc(), Group.name.asc())
        .limit(limit)
    )
    return [
        {"id": cast(int, group_id), "label": name or f"Group {group_id}", "count": cast(int, count)}
        for group_id, name, count in rows
    ]


def _route_terrain_filter_options(limit: int = 8) -> list[dict[str, object]]:
    terrain_label = func.coalesce(Route.subtype, Route.type).label("terrain")
    rows = db.session.execute(
        select(terrain_label, func.count(Route.id))
        .where(terrain_label.is_not(None))
        .group_by(terrain_label)
        .order_by(func.count(Route.id).desc(), terrain_label.asc())
        .limit(limit)
    )
    return [
        {"label": cast(str, terrain), "value": cast(str, terrain), "count": cast(int, count)}
        for terrain, count in rows
        if terrain
    ]


def _segment_terrain_filter_options(limit: int = 8) -> list[dict[str, object]]:
    terrain_label = func.coalesce(Segment.subtype, Segment.type).label("terrain")
    rows = db.session.execute(
        select(terrain_label, func.count(Segment.id))
        .where(terrain_label.is_not(None))
        .group_by(terrain_label)
        .order_by(func.count(Segment.id).desc(), terrain_label.asc())
        .limit(limit)
    )
    return [
        {"label": cast(str, terrain), "value": cast(str, terrain), "count": cast(int, count)}
        for terrain, count in rows
        if terrain
    ]


def _browser_area_search_results(query: str, limit: int = 8) -> list[dict[str, object]]:
    normalized = query.strip().lower()
    if len(normalized) < 2:
        return []

    route_center_latitude = _browser_center_latitude(Route.start_latitude, Route.end_latitude)
    route_center_longitude = _browser_center_longitude(Route.start_longitude, Route.end_longitude)
    route_label = func.concat_ws(", ", Route.city, Route.state, Route.country).label("label")
    route_rows = db.session.execute(
        select(
            route_label,
            func.count(Route.id),
            func.avg(route_center_latitude),
            func.avg(route_center_longitude),
        )
        .where(route_label != "")
        .where(func.lower(route_label).like(f"%{normalized}%"))
        .group_by(route_label)
        .order_by(func.count(Route.id).desc(), route_label.asc())
        .limit(limit)
    )

    event_label = func.concat_ws(", ", Event.town, Event.state, Event.country).label("label")
    event_rows = db.session.execute(
        select(
            event_label,
            func.count(Event.id),
            func.avg(Event.lat),
            func.avg(Event.lon),
        )
        .where(event_label != "")
        .where(func.lower(event_label).like(f"%{normalized}%"))
        .group_by(event_label)
        .order_by(func.count(Event.id).desc(), event_label.asc())
        .limit(limit)
    )

    merged: dict[str, dict[str, object]] = {}
    for label, count, latitude, longitude in list(route_rows) + list(event_rows):
        if not label or latitude is None or longitude is None:
            continue
        existing = merged.get(cast(str, label))
        if existing is None:
            merged[cast(str, label)] = {
                "count": cast(int, count),
                "label": cast(str, label),
                "lat": float(latitude),
                "lng": float(longitude),
            }
            continue
        existing["count"] = cast(int, existing["count"]) + cast(int, count)

    return sorted(
        merged.values(),
        key=lambda item: (-cast(int, item["count"]), cast(str, item["label"])),
    )[:limit]


def _route_browser_item(route: Route, *, event_count: int) -> dict[str, object]:
    favorite = _is_favorite_record(route.tags)
    center = _record_center(
        route.start_latitude,
        route.start_longitude,
        route.end_latitude,
        route.end_longitude,
        geometry_text=route.summary_polyline,
    )
    subtitle = _join_location(route.subtype or route.type, route.city, route.state)
    description = route.desc or (
        "Mapped route ready for browse-first discovery with live distance, elevation, and "
        "location-aware sorting."
    )
    return {
        "id": route.id,
        "title": route.name or f"Route {route.id}",
        "description": description,
        "subtitle": subtitle,
        "relatedPreview": {
            "clubs": [group.name or f"Group {group.id}" for group in route.groups[:3]],
            "segments": len(route.segments),
        },
        "location": _join_location(route.city, route.state, route.country),
        "favorite": favorite,
        "favoriteLabel": "Favorite" if favorite else None,
        "detailUrl": _public_detail_url("route", route.id),
        "metaLine": _format_route_meta(route),
        "searchText": " ".join(
            part
            for part in [
                route.name,
                route.desc,
                route.type,
                route.subtype,
                route.city,
                route.state,
                route.country,
                _csv_value(route.tags),
            ]
            if part
        ),
        "sortValues": {
            "closest": None,
            "duration": route.duration,
            "elevation": route.elevation_gain,
            "length": route.length,
        },
        "stats": _route_stats_bar(route) or [],
        "tags": route.tags or [],
        "center": center,
        "geometry": _browser_line_geometry(route.summary_polyline),
        "counts": [
            count
            for count in [
                _browser_count_item("clubs", len(route.groups), hide_zero=True),
                _browser_count_item("events", event_count, hide_zero=True),
                _browser_count_item("segments", len(route.segments)),
            ]
            if count is not None
        ],
    }


def _segment_browser_item(segment: Segment) -> dict[str, object]:
    favorite = _is_favorite_record(segment.tags)
    center = _record_center(
        segment.start_latitude,
        segment.start_longitude,
        segment.end_latitude,
        segment.end_longitude,
        geometry_text=segment.summary_polyline,
    )
    description = segment.desc or (
        "A defining effort ready to compare by grade, gain, duration, and where it sits in "
        "the broader route network."
    )
    return {
        "id": segment.id,
        "title": segment.name or f"Segment {segment.id}",
        "description": description,
        "subtitle": segment.subtype or segment.type,
        "relatedPreview": {
            "routes": [route.name or f"Route {route.id}" for route in segment.routes[:3]],
        },
        "location": _coordinate_pair(segment.start_latitude, segment.start_longitude),
        "favorite": favorite,
        "favoriteLabel": "Favorite" if favorite else None,
        "detailUrl": _public_detail_url("segment", segment.id),
        "metaLine": _format_segment_meta(segment),
        "searchText": " ".join(
            part
            for part in [
                segment.name,
                segment.desc,
                segment.type,
                segment.subtype,
                _csv_value(segment.tags),
            ]
            if part
        ),
        "sortValues": {
            "closest": None,
            "duration": segment.duration,
            "elevation": segment.elevation_gain,
            "length": segment.length,
        },
        "stats": _segment_stats_bar(segment) or [],
        "tags": segment.tags or [],
        "center": center,
        "geometry": _browser_line_geometry(segment.summary_polyline),
        "counts": [
            count
            for count in [
                _browser_count_item("routes", len(segment.routes)),
                _browser_count_item("images", len(segment.images)),
            ]
            if count is not None
        ],
    }


def _browser_line_geometry(geometry_text: str | None) -> dict[str, object] | None:
    if not geometry_text:
        return None
    try:
        geometry = json.loads(geometry_text)
    except json.JSONDecodeError:
        return None
    if geometry.get("type") != "LineString":
        return None
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        return None
    return cast(dict[str, object], geometry)


def _record_center(
    start_latitude: float | None,
    start_longitude: float | None,
    end_latitude: float | None,
    end_longitude: float | None,
    *,
    geometry_text: str | None,
) -> dict[str, float] | None:
    if start_latitude is not None and start_longitude is not None:
        if end_latitude is not None and end_longitude is not None:
            return {
                "lat": (start_latitude + end_latitude) / 2,
                "lng": (start_longitude + end_longitude) / 2,
            }
        return {"lat": start_latitude, "lng": start_longitude}
    geometry = _browser_line_geometry(geometry_text)
    if geometry is None:
        return None
    coordinates = cast(list[list[float]], geometry["coordinates"])
    mid_index = len(coordinates) // 2
    midpoint = coordinates[mid_index]
    return {"lat": midpoint[1], "lng": midpoint[0]}


def _browser_summary_stats(
    items: Sequence[dict[str, object]],
    *,
    secondary_label: str,
) -> list[dict[str, object]]:
    favorites = sum(1 for item in items if item.get("favorite"))
    total_related = sum(
        cast(int, count["value"])
        for item in items
        for count in cast(list[dict[str, object]], item.get("counts", []))
        if count.get("label") == secondary_label.split()[0]
    )
    geocoded = sum(1 for item in items if item.get("center") is not None)
    return [
        {"label": "Saved favorites", "value": favorites},
        {"label": secondary_label.title(), "value": total_related},
        {"label": "Map-ready records", "value": geocoded},
    ]


def _public_detail_url(entity_type: str, entity_id: int) -> str | None:
    if current_user.is_authenticated and getattr(current_user, "site_admin", False):
        return _admin_detail_url(entity_type, entity_id)
    return None


def _is_favorite_record(tags: list[str] | None) -> bool:
    if not tags:
        return False
    normalized = {tag.strip().lower() for tag in tags if tag.strip()}
    return bool({"favorite", "featured", "saved", "starred", "classic"} & normalized)


def _format_measurement_value(value: float) -> str:
    rounded = round(value, 1)
    if abs(rounded - round(rounded)) < 1e-9:
        return f"{int(round(rounded))}"
    return f"{rounded:.1f}"


def _format_distance(distance_meters: float | None) -> str | None:
    if distance_meters is None:
        return None
    distance_km = distance_meters / 1000
    if _current_unit_system() == "imperial":
        return f"{_format_measurement_value(distance_km / 1.609344)} mi"
    return f"{_format_measurement_value(distance_km)} km"


def _format_elevation(elevation_meters: float | None) -> str | None:
    if elevation_meters is None:
        return None
    if _current_unit_system() == "imperial":
        return f"{_format_measurement_value(elevation_meters * 3.28084)} ft"
    return f"{_format_measurement_value(elevation_meters)} m"


def _format_duration(duration_minutes: float | None) -> str | None:
    if duration_minutes is None:
        return None
    total_minutes = max(int(round(duration_minutes)), 0)
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def _format_grade(grade: float | None) -> str | None:
    if grade is None:
        return None
    return f"{_format_measurement_value(grade)}%"


def _format_rating(rating: float | None) -> str | None:
    if rating is None:
        return None
    return _format_measurement_value(rating)


def _is_future_datetime(value: datetime | None) -> bool:
    if value is None:
        return False
    if value.tzinfo is None:
        return value >= datetime.now(timezone.utc).replace(tzinfo=None)
    return value >= datetime.now(timezone.utc)


def _stat_item(
    label: str,
    icon: str,
    value: str | None,
    *,
    eyebrow: str | None = None,
    placeholder: str | None = None,
) -> dict[str, str] | None:
    if value is None:
        if placeholder is None:
            return None
        value = placeholder
    return {
        "eyebrow": eyebrow or label,
        "icon": icon,
        "label": label,
        "value": value,
    }


def _stats_bar(items: list[dict[str, str] | None]) -> list[dict[str, str]] | None:
    return [item for item in items if item is not None] or None


def _route_stats_bar(route: Route) -> list[dict[str, str]] | None:
    return _stats_bar(
        [
            _stat_item("Rating", "star", _format_rating(route.rating)),
            _stat_item("Distance", "distance", _format_distance(route.length)),
            _stat_item("Duration", "clock", _format_duration(route.duration)),
            _stat_item("Elevation", "mountain", _format_elevation(route.elevation_gain)),
            _stat_item("Grade", "chartup", _format_grade(route.grade)),
        ]
    )


def _segment_stats_bar(segment: Segment) -> list[dict[str, str]] | None:
    return _stats_bar(
        [
            _stat_item("Rating", "star", _format_rating(segment.rating)),
            _stat_item("Distance", "distance", _format_distance(segment.length)),
            _stat_item("Duration", "clock", _format_duration(segment.duration)),
            _stat_item("Elevation", "mountain", _format_elevation(segment.elevation_gain)),
            _stat_item("Grade", "chartup", _format_grade(segment.grade)),
        ]
    )


def _activity_stats_bar(activity: Activity) -> list[dict[str, str]] | None:
    return _stats_bar(
        [
            _stat_item("Distance", "distance", _format_distance(activity.length)),
            _stat_item("Duration", "clock", _format_duration(activity.duration)),
            _stat_item(
                "Elevation",
                "mountain",
                _format_elevation(activity.total_elevation_gain or activity.elevation_gain),
            ),
        ]
    )


def _event_stats_bar(event: Event) -> list[dict[str, str]] | None:
    route = event.route
    activity = event.activity
    linked_route = route or activity.route if activity is not None else route
    return _stats_bar(
        [
            _stat_item(
                "Rating",
                "star",
                _format_rating(linked_route.rating) if linked_route is not None else None,
            ),
            _stat_item(
                "Distance",
                "distance",
                _format_distance(
                    linked_route.length
                    if linked_route is not None
                    else activity.length
                    if activity is not None
                    else None
                ),
            ),
            _stat_item(
                "Duration",
                "clock",
                _format_duration(
                    event.duration
                    if event.duration is not None
                    else linked_route.duration
                    if linked_route is not None
                    else activity.duration
                    if activity is not None
                    else None
                ),
            ),
            _stat_item(
                "Elevation",
                "mountain",
                _format_elevation(
                    linked_route.elevation_gain
                    if linked_route is not None
                    else activity.total_elevation_gain
                    if activity is not None and activity.total_elevation_gain is not None
                    else activity.elevation_gain
                    if activity is not None
                    else None
                ),
            ),
            _stat_item(
                "Grade",
                "chartup",
                _format_grade(linked_route.grade) if linked_route is not None else None,
            ),
        ]
    )


def _calendar_stats_bar(calendar: Calendar) -> list[dict[str, str]] | None:
    upcoming_count = sum(1 for event in calendar.events if _is_future_datetime(event.date_start))
    return _stats_bar(
        [
            _stat_item("Events", "calendar", _display_value(len(calendar.events))),
            _stat_item("Upcoming", "clock", _display_value(upcoming_count)),
            _stat_item(
                "Group",
                "distance",
                calendar.group.name if calendar.group is not None else None,
            ),
        ]
    )


def _format_route_meta(route: Route) -> str | None:
    return _join_location(
        route.subtype or route.type,
        _format_distance(route.length),
        _format_elevation(route.elevation_gain),
    )


def _format_segment_meta(segment: Segment) -> str | None:
    return _join_location(
        segment.subtype or segment.type,
        _format_distance(segment.length),
        _format_elevation(segment.elevation_gain),
    )


def _image_preview_url(image: Image) -> str | None:
    return image.img_large or image.img_medium or image.img_small or image.img_thumb or image.url


def _route_media_previews(route: Route) -> list[dict[str, str]] | None:
    preview_items: list[tuple[str, str | None]] = [("Map thumbnail", route.map_thumbnail)]
    for segment in route.segments[:3]:
        for image in segment.images[:1]:
            preview_items.append(
                (
                    f"Segment image: {segment.name or 'Segment'}",
                    _image_preview_url(image),
                )
            )
    return _media_previews(preview_items)


def _segment_media_previews(segment: Segment) -> list[dict[str, str]] | None:
    preview_items = [
        (image.title or image.caption or f"Image {image.id}", _image_preview_url(image))
        for image in segment.images[:4]
    ]
    return _media_previews(preview_items)


def _event_media_previews(event: Event) -> list[dict[str, str]] | None:
    preview_items: list[tuple[str, str | None]] = [
        ("Photo", event.photo_url),
        ("Logo", event.logo),
        ("Profile photo", event.profile_photo),
    ]
    preview_items.extend(
        (image.title or image.caption or f"Image {image.id}", _image_preview_url(image))
        for image in event.images[:3]
    )
    return _media_previews(preview_items)


def _point_of_interest_media_previews(point: PointOfInterest) -> list[dict[str, str]] | None:
    preview_items = [
        (image.title or image.caption or f"Image {image.id}", _image_preview_url(image))
        for image in point.images[:4]
    ]
    return _media_previews(preview_items)


def _activity_media_previews(activity: Activity) -> list[dict[str, str]] | None:
    preview_items: list[tuple[str, str | None]] = [("Photo", activity.photo_url)]
    preview_items.extend(
        (image.title or image.caption or f"Image {image.id}", _image_preview_url(image))
        for image in activity.images[:3]
    )
    return _media_previews(preview_items)


def _media_previews(items: list[tuple[str, str | None]]) -> list[dict[str, str]] | None:
    previews = [
        {"alt": label, "label": label, "url": url}
        for label, url in items
        if url is not None and url.strip()
    ]
    return previews or None


def _line_coordinates(geometry_text: str | None) -> list[tuple[float, float]] | None:
    if geometry_text is None:
        return None
    stripped = geometry_text.strip()
    if not stripped:
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    geometry_payload = payload.get("geometry") if payload.get("type") == "Feature" else payload
    coordinates = (
        geometry_payload.get("coordinates") if isinstance(geometry_payload, dict) else None
    )
    if not isinstance(coordinates, list):
        return None
    points: list[tuple[float, float]] = []
    for coordinate in coordinates:
        if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 2:
            continue
        try:
            longitude = float(coordinate[0])
            latitude = float(coordinate[1])
        except (TypeError, ValueError):
            continue
        points.append((longitude, latitude))
    return points or None


def _leaflet_latlngs(geometry_text: str | None) -> list[list[float]] | None:
    coordinates = _line_coordinates(geometry_text)
    if coordinates is None:
        return None
    return [[latitude, longitude] for longitude, latitude in coordinates]


def _svg_path_from_points(
    points: Sequence[tuple[float, float]],
    *,
    width: int = 640,
    height: int = 280,
    padding: int = 20,
) -> dict[str, object] | None:
    if len(points) < 2:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    x_span = max(max_x - min_x, 1e-9)
    y_span = max(max_y - min_y, 1e-9)
    usable_width = width - (padding * 2)
    usable_height = height - (padding * 2)
    svg_points = []
    for x_value, y_value in points:
        scaled_x = padding + ((x_value - min_x) / x_span) * usable_width
        scaled_y = height - padding - ((y_value - min_y) / y_span) * usable_height
        svg_points.append((scaled_x, scaled_y))
    path = " ".join(
        f"{'M' if index == 0 else 'L'} {x_value:.2f} {y_value:.2f}"
        for index, (x_value, y_value) in enumerate(svg_points)
    )
    return {
        "height": height,
        "path": path,
        "points": svg_points,
        "start": {"x": f"{svg_points[0][0]:.2f}", "y": f"{svg_points[0][1]:.2f}"},
        "view_box": f"0 0 {width} {height}",
        "width": width,
    }


def _sample_points(
    svg_points: Sequence[tuple[float, float]],
    *,
    labels: Sequence[str] | None = None,
    max_points: int = 8,
) -> list[dict[str, str]]:
    if not svg_points:
        return []
    if len(svg_points) <= max_points:
        indices = list(range(len(svg_points)))
    else:
        indices = sorted(
            {round(index * (len(svg_points) - 1) / (max_points - 1)) for index in range(max_points)}
        )
    samples: list[dict[str, str]] = []
    for index in indices:
        label = (
            labels[index] if labels is not None and index < len(labels) else f"Point {index + 1}"
        )
        samples.append(
            {
                "index": str(index),
                "label": label,
                "x": f"{svg_points[index][0]:.2f}",
                "y": f"{svg_points[index][1]:.2f}",
            }
        )
    return samples


def _elevation_profile(elevations: list[float] | None) -> dict[str, object] | None:
    if elevations is None or len(elevations) < 2:
        return None
    points = [(float(index), float(value)) for index, value in enumerate(elevations)]
    line = _svg_path_from_points(points, height=220, padding=18)
    if line is None:
        return None
    min_value = min(elevations)
    max_value = max(elevations)
    baseline = 220 - 18
    width = cast(int, line["width"])
    path = cast(str, line["path"])
    svg_points = cast(list[tuple[float, float]], line["points"])
    area_path = f"{path} L {width - 18:.2f} {baseline:.2f} L 18.00 {baseline:.2f} Z"
    return {
        "area_path": area_path,
        "max_label": _display_value(max_value),
        "min_label": _display_value(min_value),
        "path": path,
        "samples": _sample_points(
            svg_points,
            labels=[_display_value(value) or "0" for value in elevations],
        ),
        "view_box": cast(str, line["view_box"]),
    }


def _line_layer(
    geometry_text: str | None,
    *,
    label: str,
) -> dict[str, object] | None:
    latlngs = _leaflet_latlngs(geometry_text)
    if latlngs is None:
        return None
    return {
        "latlngs": latlngs,
        "label": label,
    }


def _marker_entry(
    entity_id: int,
    entity_type: str | None,
    latitude: float | None,
    longitude: float | None,
    *,
    title: str | None = None,
) -> dict[str, object] | None:
    if latitude is None or longitude is None:
        return None
    return {
        "entity_id": entity_id,
        "entity_type": entity_type or "route",
        "latlng": [latitude, longitude],
        "title": title,
    }


def _marker_layer(
    *,
    label: str,
    markers: Sequence[dict[str, object] | None],
) -> dict[str, object] | None:
    visible_markers = [marker for marker in markers if marker is not None]
    if not visible_markers:
        return None
    return {
        "label": label,
        "markers": visible_markers,
    }


def _paths_layer(
    *,
    label: str,
    geometries: Sequence[str | None],
    markers: Sequence[dict[str, object] | None] | None = None,
) -> dict[str, object] | None:
    paths = [
        latlngs
        for geometry in geometries
        for latlngs in [_leaflet_latlngs(geometry)]
        if latlngs is not None
    ]
    layer_markers = [marker for marker in (markers or []) if marker is not None]
    if not paths and not layer_markers:
        return None
    payload: dict[str, object] = {"label": label}
    if paths:
        payload["paths"] = paths
    if layer_markers:
        payload["markers"] = layer_markers
    return payload


def _line_visual(
    geometry_text: str | None,
    *,
    eyebrow: str,
    title: str,
    body: str,
) -> dict[str, object] | None:
    layer = _line_layer(geometry_text, label=title)
    if layer is None:
        return None
    return {
        "body": body,
        "eyebrow": eyebrow,
        "kind": "map",
        "layers": [layer],
        "title": title,
    }


def _multi_line_visual(
    *,
    eyebrow: str,
    title: str,
    body: str,
    layers: Sequence[tuple[str, str | None]],
) -> dict[str, object] | None:
    line_layers = [
        layer
        for label, geometry_text in layers
        for layer in [_line_layer(geometry_text, label=label)]
        if layer is not None
    ]
    if not line_layers:
        return None
    return {
        "body": body,
        "eyebrow": eyebrow,
        "kind": "map",
        "layers": line_layers,
        "title": title,
    }


def _layered_map_visual(
    *,
    eyebrow: str,
    title: str,
    body: str,
    layers: Sequence[dict[str, object] | None],
) -> dict[str, object] | None:
    valid_layers = [layer for layer in layers if layer is not None]
    if not valid_layers:
        return None
    return {
        "body": body,
        "eyebrow": eyebrow,
        "kind": "map",
        "layers": valid_layers,
        "title": title,
    }


def _start_marker(
    entity_id: int,
    entity_type: str | None,
    latitude: float | None,
    longitude: float | None,
) -> dict[str, object] | None:
    if latitude is None or longitude is None:
        return None
    return {
        "entity_id": entity_id,
        "entity_type": entity_type or "route",
        "latlng": [latitude, longitude],
    }


def _profile_visual(
    elevations: list[float] | None,
    *,
    eyebrow: str,
    title: str,
    body: str,
) -> dict[str, object] | None:
    profile = _elevation_profile(elevations)
    if profile is None:
        return None
    return {
        "body": body,
        "eyebrow": eyebrow,
        "kind": "profile",
        "elevations": elevations,
        "profile": profile,
        "title": title,
    }


def _admin_detail_url(entity_type: str, entity_id: int | None) -> str | None:
    if entity_id is None:
        return None

    endpoint_map = {
        "user": "core.admin_user_detail_route",
        "group": "core.admin_group_detail_route",
        "calendar": "core.admin_calendar_detail_route",
        "route": "core.admin_route_detail_route",
        "segment": "core.admin_segment_detail_route",
        "event": "core.admin_event_detail_route",
        "point_of_interest": "core.admin_point_of_interest_detail_route",
        "activity": "core.admin_activity_detail_route",
    }
    endpoint = endpoint_map.get(entity_type)
    if endpoint is None:
        return None

    if entity_type == "user":
        return url_for(endpoint, user_id=entity_id)
    if entity_type == "group":
        return url_for(endpoint, group_id=entity_id)
    if entity_type == "calendar":
        return url_for(endpoint, calendar_id=entity_id)
    if entity_type == "route":
        return url_for(endpoint, route_id=entity_id)
    if entity_type == "segment":
        return url_for(endpoint, segment_id=entity_id)
    if entity_type == "event":
        return url_for(endpoint, event_id=entity_id)
    if entity_type == "point_of_interest":
        return url_for(endpoint, point_id=entity_id)
    return url_for(endpoint, activity_id=entity_id)


def _detail_rows(
    raw_rows: Sequence[tuple[str, object | None] | tuple[str, object | None, str | None]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for raw_row in raw_rows:
        if len(raw_row) == 2:
            label, value = raw_row
            url = None
        else:
            label, value, url = raw_row

        display_value = _display_value(value)
        if display_value is None:
            continue
        rows.append({"label": label, "value": display_value, "url": url})
    return rows


def _story_section(
    title: str,
    *,
    eyebrow: str,
    body: str | None = None,
    items: list[tuple[str, object | None]] | None = None,
) -> dict[str, object] | None:
    section_items = _detail_rows(items or [])
    if body is None and not section_items:
        return None
    return {
        "body": _display_value(body),
        "eyebrow": eyebrow,
        "items": section_items,
        "title": title,
    }


def _related_section(
    title: str,
    *,
    eyebrow: str,
    empty_copy: str,
    items: list[dict[str, object]],
) -> dict[str, object] | None:
    if not items:
        return None
    return {
        "eyebrow": eyebrow,
        "empty_copy": empty_copy,
        "items": items,
        "title": title,
    }


def _route_story_sections(route: Route) -> list[dict[str, object]] | None:
    sections = [
        _story_section(
            "Why riders save this one",
            eyebrow="Route notes",
            body=route.desc
            or (
                "No route description is stored yet, but the core shape and geography "
                "are already on the record."
            ),
        ),
        _story_section(
            "Route shape",
            eyebrow="Start to finish",
            items=[
                ("Starts", _coordinate_pair(route.start_latitude, route.start_longitude)),
                ("Finishes", _coordinate_pair(route.end_latitude, route.end_longitude)),
                ("Address", route.address),
                ("Place", _join_location(route.city, route.state, route.country)),
            ],
        ),
    ]
    return [section for section in sections if section is not None] or None


def _segment_story_sections(segment: Segment) -> list[dict[str, object]] | None:
    sections = [
        _story_section(
            "What this segment asks of a rider",
            eyebrow="Segment notes",
            body=segment.desc
            or (
                "No segment description is stored yet, but the elevation and geometry "
                "fields give us the shape of the effort."
            ),
        ),
        _story_section(
            "Profile and shape",
            eyebrow="Effort",
            items=[
                ("Starts", _coordinate_pair(segment.start_latitude, segment.start_longitude)),
                ("Finishes", _coordinate_pair(segment.end_latitude, segment.end_longitude)),
                ("Elevation loss", segment.elevation_loss),
                ("High point", segment.elev_high),
                ("Low point", segment.elev_low),
                ("Max speed", segment.track_maxspeed),
            ],
        ),
    ]
    return [section for section in sections if section is not None] or None


def _route_related_sections(route: Route) -> list[dict[str, object]] | None:
    sections = [
        _related_section(
            "Linked groups",
            eyebrow="Where this route lives",
            empty_copy="This route is not linked to any groups yet.",
            items=[
                {
                    "eyebrow": "Group",
                    "external": False,
                    "href": url_for("core.admin_group_detail_route", group_id=group.id),
                    "meta": _join_location(
                        group.about_blurb,
                        _join_location(group.home_town, group.home_state, group.home_country),
                    ),
                    "title": group.name or f"Group {group.id}",
                }
                for group in route.groups
            ],
        ),
        _related_section(
            "Linked segments",
            eyebrow="Building blocks",
            empty_copy="This route is not linked to any segments yet.",
            items=[
                {
                    "eyebrow": "Segment",
                    "external": False,
                    "href": url_for("core.admin_segment_detail_route", segment_id=segment.id),
                    "meta": _format_segment_meta(segment),
                    "title": segment.name or f"Segment {segment.id}",
                }
                for segment in route.segments
            ],
        ),
        _related_section(
            "External links",
            eyebrow="Source material",
            empty_copy="This route does not have external links yet.",
            items=[
                {
                    "eyebrow": link.type or "Link",
                    "external": True,
                    "href": link.url,
                    "meta": _join_location(link.subtype, link.description),
                    "title": link.name or link.url or f"Link {link.id}",
                }
                for link in route.links
                if link.url
            ],
        ),
    ]
    return [section for section in sections if section is not None] or None


def _segment_related_sections(segment: Segment) -> list[dict[str, object]] | None:
    sections = [
        _related_section(
            "Linked routes",
            eyebrow="Appears in",
            empty_copy="This segment is not linked to any routes yet.",
            items=[
                {
                    "eyebrow": "Route",
                    "external": False,
                    "href": url_for("core.admin_route_detail_route", route_id=route.id),
                    "meta": _format_route_meta(route),
                    "title": route.name or f"Route {route.id}",
                }
                for route in segment.routes
            ],
        ),
        _related_section(
            "Image set",
            eyebrow="Visual context",
            empty_copy="This segment does not have images yet.",
            items=[
                {
                    "eyebrow": "Image",
                    "external": True,
                    "href": _image_preview_url(image),
                    "meta": _join_location(image.caption, image.alt_txt),
                    "title": image.title or f"Image {image.id}",
                }
                for image in segment.images
                if _image_preview_url(image)
            ],
        ),
    ]
    return [section for section in sections if section is not None] or None


def _route_visual_sections(route: Route) -> list[dict[str, object]] | None:
    sections = [
        _multi_line_visual(
            eyebrow="Map",
            title="Route view",
            body=(
                "The route opens with an interactive map panel, carrying forward the "
                "original page rhythm while staying inside the lighter stack."
            ),
            layers=[
                ("Summary line", route.summary_polyline),
                ("Full track", route.full_track),
            ],
        ),
        _profile_visual(
            route.elevation_array,
            eyebrow="Elevation",
            title="Elevation profile",
            body=(
                "The climbing profile stays near the map, so the route reads like effort "
                "and shape together rather than separate widgets."
            ),
        ),
    ]
    if sections[0] is not None:
        sections[0]["marker"] = _start_marker(
            route.id,
            route.type,
            route.start_latitude,
            route.start_longitude,
        )
    return [section for section in sections if section is not None] or None


def _segment_visual_sections(segment: Segment) -> list[dict[str, object]] | None:
    sections = [
        _multi_line_visual(
            eyebrow="Map",
            title="Segment line",
            body=(
                "Segments need the same spatial clarity as full routes, especially when "
                "they represent the defining climb or connector."
            ),
            layers=[
                ("Summary line", segment.summary_polyline),
                ("Full track", segment.full_track),
            ],
        ),
        _profile_visual(
            segment.elevation_array
            or [value for value in [segment.elev_low, segment.elev_high] if value is not None],
            eyebrow="Elevation",
            title="Segment profile",
            body="A tighter profile puts the pitch and vertical shape front and center.",
        ),
    ]
    if sections[0] is not None:
        sections[0]["marker"] = _start_marker(
            segment.id,
            segment.type,
            segment.start_latitude,
            segment.start_longitude,
        )
    return [section for section in sections if section is not None] or None


def _activity_visual_sections(activity: Activity) -> list[dict[str, object]] | None:
    sections = [
        _line_visual(
            activity.summary_polyline or activity.full_track,
            eyebrow="Map",
            title="Activity trace",
            body=(
                "A simplified line rendering of the recorded ride so the movement data "
                "feels present on the page."
            ),
        ),
        _profile_visual(
            [
                value
                for value in [activity.elev_low, activity.elevation_gain, activity.elev_high]
                if value is not None
            ]
            if activity.elev_low is not None or activity.elev_high is not None
            else None,
            eyebrow="Effort",
            title="Climbing shape",
            body=(
                "A compact profile based on the stored elevation markers, keeping the "
                "effort story visible even when a full sample array is not available."
            ),
        ),
    ]
    if sections[0] is not None:
        sections[0]["marker"] = _start_marker(
            activity.id,
            activity.type,
            activity.start_latitude,
            activity.start_longitude,
        )
    return [section for section in sections if section is not None] or None


def _event_visual_sections(event: Event) -> list[dict[str, object]] | None:
    linked_route = event.route or (event.activity.route if event.activity is not None else None)
    sections = [
        _layered_map_visual(
            eyebrow="Map",
            title="Event footprint",
            body=(
                "Events should feel situated in the same spatial language as routes, with the "
                "location and linked ride context visible together."
            ),
            layers=[
                _marker_layer(
                    label="Event location",
                    markers=[
                        _marker_entry(
                            event.id,
                            event.type or "event",
                            event.lat,
                            event.lon,
                            title=event.name,
                        )
                    ],
                ),
                _paths_layer(
                    label="Linked route",
                    geometries=[
                        linked_route.summary_polyline if linked_route is not None else None,
                        linked_route.full_track if linked_route is not None else None,
                    ],
                    markers=[
                        _marker_entry(
                            event.id,
                            event.type or "event",
                            event.lat,
                            event.lon,
                            title=event.name,
                        ),
                        _marker_entry(
                            linked_route.id,
                            linked_route.type,
                            linked_route.start_latitude,
                            linked_route.start_longitude,
                            title=linked_route.name,
                        )
                        if linked_route is not None
                        else None,
                    ],
                ),
                _paths_layer(
                    label="Linked activity",
                    geometries=[
                        event.activity.summary_polyline if event.activity is not None else None,
                        event.activity.full_track if event.activity is not None else None,
                    ],
                    markers=[
                        _marker_entry(
                            event.id,
                            event.type or "event",
                            event.lat,
                            event.lon,
                            title=event.name,
                        ),
                        _marker_entry(
                            event.activity.id,
                            event.activity.type,
                            event.activity.start_latitude,
                            event.activity.start_longitude,
                            title=event.activity.name,
                        )
                        if event.activity is not None
                        else None,
                    ],
                ),
            ],
        )
    ]
    return [section for section in sections if section is not None] or None


def _calendar_visual_sections(calendar: Calendar) -> list[dict[str, object]] | None:
    event_markers = [
        _marker_entry(
            event.id,
            event.type or "event",
            event.lat,
            event.lon,
            title=event.name,
        )
        for event in calendar.events
    ]
    route_geometries: list[str | None] = []
    for event in calendar.events:
        if event.route is not None:
            route_geometries.extend([event.route.summary_polyline, event.route.full_track])
        if event.activity is not None:
            route_geometries.extend([event.activity.summary_polyline, event.activity.full_track])

    sections = [
        _layered_map_visual(
            eyebrow="Map",
            title="Calendar footprint",
            body=(
                "Calendars should read as spatial programs, not just lists: the upcoming points "
                "and linked route network live together on the map."
            ),
            layers=[
                _marker_layer(label="Event markers", markers=event_markers),
                _paths_layer(
                    label="Route network",
                    geometries=route_geometries,
                    markers=event_markers,
                ),
            ],
        )
    ]
    return [section for section in sections if section is not None] or None


def _calendar_story_sections(calendar: Calendar) -> list[dict[str, object]] | None:
    sections = [
        _story_section(
            "What this calendar holds",
            eyebrow="Calendar notes",
            body=calendar.description
            or (
                "This calendar anchors a set of events even if a fuller curator note has not "
                "been written yet."
            ),
        ),
        _story_section(
            "Program shape",
            eyebrow="Coverage",
            items=[
                ("Primary activity", calendar.primary_activity),
                ("Type", calendar.type),
                ("Subtype", calendar.subtype),
                ("Linked group", calendar.group.name if calendar.group is not None else None),
                ("Events", len(calendar.events)),
            ],
        ),
    ]
    return [section for section in sections if section is not None] or None


def _event_story_sections(event: Event) -> list[dict[str, object]] | None:
    sections = [
        _story_section(
            "Why this event exists",
            eyebrow="Event notes",
            body=event.description
            or (
                "The event is on the calendar, even if the fuller event brief has not "
                "been written yet."
            ),
        ),
        _story_section(
            "When and where",
            eyebrow="Timing",
            items=[
                ("Starts", event.date_start),
                ("Ends", event.date_end),
                ("Place", _join_location(event.town, event.state, event.country)),
                ("Coordinates", _coordinate_pair(event.lat, event.lon)),
            ],
        ),
    ]
    return [section for section in sections if section is not None] or None


def _point_of_interest_story_sections(point: PointOfInterest) -> list[dict[str, object]] | None:
    sections = [
        _story_section(
            "Why it matters on the map",
            eyebrow="Point notes",
            body=point.description
            or (
                "This point is stored as a named waypoint even if the descriptive "
                "context is still sparse."
            ),
        ),
        _story_section(
            "Location",
            eyebrow="Map context",
            items=[
                ("Coordinates", _coordinate_pair(point.lat, point.lon)),
                ("Geometry", point.geoll),
                ("Reference URL", point.url),
            ],
        ),
    ]
    return [section for section in sections if section is not None] or None


def _activity_story_sections(activity: Activity) -> list[dict[str, object]] | None:
    sections = [
        _story_section(
            "What happened out there",
            eyebrow="Activity notes",
            body=activity.desc
            or (
                "The recorded metrics are in place even if a fuller ride summary has "
                "not been added yet."
            ),
        ),
        _story_section(
            "Effort profile",
            eyebrow="Performance",
            items=[
                ("Starts", activity.start_date),
                ("Ends", activity.end_date),
                ("Start", _coordinate_pair(activity.start_latitude, activity.start_longitude)),
                ("Finish", _coordinate_pair(activity.end_latitude, activity.end_longitude)),
                ("Moving time", activity.moving_time),
            ],
        ),
    ]
    return [section for section in sections if section is not None] or None


def _event_related_sections(event: Event) -> list[dict[str, object]] | None:
    sections = [
        _related_section(
            "Linked route and activity",
            eyebrow="Program",
            empty_copy="This event is not linked to a route or activity yet.",
            items=[
                *(
                    [
                        {
                            "eyebrow": "Route",
                            "external": False,
                            "href": url_for(
                                "core.admin_route_detail_route",
                                route_id=event.route.id,
                            ),
                            "meta": _format_route_meta(event.route),
                            "title": event.route.name or f"Route {event.route.id}",
                        }
                    ]
                    if event.route is not None
                    else []
                ),
                *(
                    [
                        {
                            "eyebrow": "Activity",
                            "external": False,
                            "href": url_for(
                                "core.admin_activity_detail_route",
                                activity_id=event.activity.id,
                            ),
                            "meta": _join_location(
                                event.activity.subtype or event.activity.type,
                                _display_value(event.activity.length),
                            ),
                            "title": event.activity.name or f"Activity {event.activity.id}",
                        }
                    ]
                    if event.activity is not None
                    else []
                ),
            ],
        ),
        _related_section(
            "Calendars and fees",
            eyebrow="Operations",
            empty_copy="This event is not connected to calendars or fees yet.",
            items=[
                *[
                    {
                        "eyebrow": "Calendar",
                        "external": False,
                        "href": url_for(
                            "core.admin_calendar_detail_route", calendar_id=calendar.id
                        ),
                        "meta": _join_location(
                            calendar.primary_activity,
                            calendar.type,
                            calendar.subtype,
                        ),
                        "title": calendar.name or f"Calendar {calendar.id}",
                    }
                    for calendar in event.calendars
                ],
                *[
                    {
                        "eyebrow": "Fee",
                        "external": False,
                        "href": url_for("core.admin_fee_detail_route", fee_id=fee.id),
                        "meta": _join_location(_display_value(fee.fee), fee.description),
                        "title": fee.name or f"Fee {fee.id}",
                    }
                    for fee in event.fees
                ],
            ],
        ),
        _related_section(
            "Participants",
            eyebrow="Attendance",
            empty_copy="No participants are attached to this event yet.",
            items=[
                {
                    "eyebrow": participant.status.name if participant.status else "Participant",
                    "external": False,
                    "href": url_for("core.admin_user_detail_route", user_id=participant.user.id),
                    "meta": _join_location(
                        _display_value(participant.rsvp_date),
                        _display_value(participant.fee_paid_date),
                    ),
                    "title": participant.user.display_name,
                }
                for participant in event.participants
                if participant.user is not None
            ],
        ),
    ]
    return [section for section in sections if section is not None] or None


def _calendar_related_sections(calendar: Calendar) -> list[dict[str, object]] | None:
    sections = [
        _related_section(
            "Linked group and events",
            eyebrow="Program",
            empty_copy="This calendar does not have linked records yet.",
            items=[
                *(
                    [
                        {
                            "eyebrow": "Group",
                            "external": False,
                            "href": url_for(
                                "core.admin_group_detail_route", group_id=calendar.group.id
                            ),
                            "meta": _join_location(
                                calendar.group.primary_activity,
                                _join_location(
                                    calendar.group.home_town,
                                    calendar.group.home_state,
                                    calendar.group.home_country,
                                ),
                            ),
                            "title": calendar.group.name or f"Group {calendar.group.id}",
                        }
                    ]
                    if calendar.group is not None
                    else []
                ),
                *[
                    {
                        "eyebrow": "Event",
                        "external": False,
                        "href": url_for("core.admin_event_detail_route", event_id=event.id),
                        "meta": _join_location(
                            _display_value(event.date_start),
                            _join_location(event.town, event.state, event.country),
                        ),
                        "title": event.name or f"Event {event.id}",
                    }
                    for event in sorted(
                        calendar.events,
                        key=lambda event: event.date_start
                        or datetime.min.replace(tzinfo=timezone.utc),
                    )
                ],
            ],
        )
    ]
    return [section for section in sections if section is not None] or None


def _point_of_interest_related_sections(point: PointOfInterest) -> list[dict[str, object]] | None:
    sections = [
        _related_section(
            "Image set",
            eyebrow="Visual context",
            empty_copy="This point does not have images yet.",
            items=[
                {
                    "eyebrow": "Image",
                    "external": True,
                    "href": _image_preview_url(image),
                    "meta": _join_location(image.caption, image.alt_txt),
                    "title": image.title or f"Image {image.id}",
                }
                for image in point.images
                if _image_preview_url(image)
            ],
        ),
    ]
    return [section for section in sections if section is not None] or None


def _activity_related_sections(activity: Activity) -> list[dict[str, object]] | None:
    sections = [
        _related_section(
            "Linked route",
            eyebrow="Route context",
            empty_copy="This activity is not linked to a route yet.",
            items=[
                {
                    "eyebrow": "Route",
                    "external": False,
                    "href": url_for("core.admin_route_detail_route", route_id=activity.route.id),
                    "meta": _format_route_meta(activity.route),
                    "title": activity.route.name or f"Route {activity.route.id}",
                }
                for _ in [activity.route]
                if activity.route is not None
            ],
        ),
        _related_section(
            "Image set",
            eyebrow="Ride media",
            empty_copy="This activity does not have images yet.",
            items=[
                {
                    "eyebrow": "Image",
                    "external": True,
                    "href": _image_preview_url(image),
                    "meta": _join_location(image.caption, image.alt_txt),
                    "title": image.title or f"Image {image.id}",
                }
                for image in activity.images
                if _image_preview_url(image)
            ],
        ),
    ]
    return [section for section in sections if section is not None] or None


def _edit_text_field(
    name: str,
    label: str,
    value: object | None,
    *,
    kind: str = "text",
    suggestions: list[dict[str, object]] | None = None,
    help_text: str | None = None,
) -> dict[str, object]:
    return {
        "help_text": help_text,
        "kind": kind,
        "label": label,
        "name": name,
        "suggestions": suggestions,
        "value": _display_value(value) or "",
    }


def _edit_related_field(
    name: str,
    label: str,
    value: object | None,
    *,
    model: type[ModelT],
    title_getter: Callable[[ModelT], str],
    help_text: str | None = None,
) -> dict[str, object]:
    suggestions = [
        {
            "label": f"{cast(int, getattr(record, 'id'))}: {title_getter(record)}",
            "value": cast(int, getattr(record, "id")),
        }
        for record in _recent_records(model, limit=8)
    ]
    return _edit_text_field(
        name,
        label,
        value,
        suggestions=suggestions or None,
        help_text=help_text or "Use an existing record ID or choose from recent suggestions.",
    )


def _edit_textarea_field(
    name: str, label: str, value: object | None, *, rows: int = 5
) -> dict[str, object]:
    return {
        "kind": "textarea",
        "label": label,
        "name": name,
        "rows": rows,
        "value": _display_value(value) or "",
    }


def _edit_checkbox_field(name: str, label: str, checked: bool | None) -> dict[str, object]:
    return {"checked": bool(checked), "kind": "checkbox", "label": label, "name": name}


def _image_fields(image: Image | None) -> list[dict[str, object]]:
    return [
        _edit_related_field(
            "photographer_id",
            "Photographer ID",
            image.photographer_id if image else None,
            model=User,
            title_getter=lambda user: user.display_name,
        ),
        _edit_related_field(
            "group_id",
            "Group ID",
            image.group_id if image else None,
            model=Group,
            title_getter=lambda group: group.name or "Group",
        ),
        _edit_related_field(
            "segment_id",
            "Segment ID",
            image.segment_id if image else None,
            model=Segment,
            title_getter=lambda segment: segment.name or "Segment",
        ),
        _edit_related_field(
            "activity_id",
            "Activity ID",
            image.activity_id if image else None,
            model=Activity,
            title_getter=lambda activity: activity.name or "Activity",
        ),
        _edit_text_field("title", "Title", image.title if image else None),
        _edit_text_field("caption", "Caption", image.caption if image else None),
        _edit_text_field("alt_txt", "Alt text", image.alt_txt if image else None),
        _edit_text_field("img_small", "Small image URL", image.img_small if image else None),
        _edit_text_field("img_medium", "Medium image URL", image.img_medium if image else None),
        _edit_text_field("img_large", "Large image URL", image.img_large if image else None),
        _edit_text_field("img_thumb", "Thumb image URL", image.img_thumb if image else None),
        _edit_text_field("url", "Canonical URL", image.url if image else None),
        _edit_text_field("latlng", "Latlng", image.latlng if image else None),
        _edit_text_field("geoll", "Geometry", image.geoll if image else None),
        _edit_text_field(
            "tags",
            "Tags (comma separated)",
            _csv_value(image.tags if image else None),
        ),
    ]


def _link_fields(link: GroupExternalUrl | None) -> list[dict[str, object]]:
    return [
        _edit_related_field(
            "group_id",
            "Group ID",
            link.group_id if link else None,
            model=Group,
            title_getter=lambda group: group.name or "Group",
            help_text="Choose either a group or a route owner.",
        ),
        _edit_related_field(
            "route_id",
            "Route ID",
            link.route_id if link else None,
            model=Route,
            title_getter=lambda route: route.name or "Route",
            help_text="Choose either a route or a group owner.",
        ),
        _edit_text_field("name", "Name", link.name if link else None),
        _edit_text_field("type", "Type", link.type if link else None),
        _edit_text_field("subtype", "Subtype", link.subtype if link else None),
        _edit_text_field("url", "URL", link.url if link else None),
        _edit_textarea_field("description", "Description", link.description if link else None),
        _edit_text_field("icon", "Icon", link.icon if link else None),
        _edit_text_field("img", "Image URL", link.img if link else None),
        _edit_text_field("tags", "Tags (comma separated)", _csv_value(link.tags if link else None)),
    ]


def _dues_fields(dues: GroupDues | None) -> list[dict[str, object]]:
    return [
        _edit_related_field(
            "group_id",
            "Group ID",
            dues.group_id if dues else None,
            model=Group,
            title_getter=lambda group: group.name or "Group",
        ),
        _edit_text_field("name", "Name", dues.name if dues else None),
        _edit_text_field("fee", "Fee", dues.fee if dues else None),
        _edit_text_field("duration", "Duration", dues.duration if dues else None),
        _edit_textarea_field("description", "Description", dues.description if dues else None),
        _edit_text_field("tags", "Tags (comma separated)", _csv_value(dues.tags if dues else None)),
    ]


def _fee_fields(fee: EventFee | None) -> list[dict[str, object]]:
    return [
        _edit_related_field(
            "event_id",
            "Event ID",
            fee.event_id if fee else None,
            model=Event,
            title_getter=lambda event: event.name or "Event",
        ),
        _edit_text_field("name", "Name", fee.name if fee else None),
        _edit_text_field("fee", "Fee", fee.fee if fee else None),
        _edit_text_field("duration", "Duration", fee.duration if fee else None),
        _edit_textarea_field("description", "Description", fee.description if fee else None),
        _edit_text_field("tags", "Tags (comma separated)", _csv_value(fee.tags if fee else None)),
    ]


def _display_value(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.strftime("%Y-%m-%d %H:%M UTC")
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else None
    text = str(value).strip()
    return text or None


def _csv_value(values: list[str] | None) -> str:
    return ", ".join(values or [])


def _csv_number_value(values: list[float] | None) -> str:
    return ", ".join(f"{value:g}" for value in (values or []))


def _nullable_bool_value(value: bool | None) -> str:
    if value is None:
        return ""
    return "true" if value else "false"


def _join_location(*parts: str | None) -> str | None:
    normalized = [part.strip() for part in parts if part and part.strip()]
    return ", ".join(normalized) if normalized else None


def _combine_tags(*groups: list[str] | None) -> list[str] | None:
    combined: list[str] = []
    for group in groups:
        if group is None:
            continue
        for tag in group:
            if tag not in combined:
                combined.append(tag)
    return combined or None


def _form_required_str(name: str) -> str:
    value = request.form.get(name, "").strip()
    if not value:
        raise AdminFormError(f"{_field_label(name)} is required.")
    return value


def _form_optional_str(name: str) -> str | None:
    value = request.form.get(name, "").strip()
    return value or None


def _form_optional_float(name: str) -> float | None:
    raw_value = request.form.get(name, "").strip()
    if not raw_value:
        return None
    try:
        return float(raw_value)
    except ValueError:
        raise AdminFormError(f"{_field_label(name)} must be a number.")


def _form_required_float(name: str) -> float:
    value = _form_optional_float(name)
    if value is None:
        raise AdminFormError(f"{_field_label(name)} is required.")
    return value


def _form_optional_int(name: str) -> int | None:
    raw_value = request.form.get(name, "").strip()
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except ValueError:
        raise AdminFormError(f"{_field_label(name)} must be a whole number.")


def _form_required_int(name: str) -> int:
    value = _form_optional_int(name)
    if value is None:
        raise AdminFormError(f"{_field_label(name)} is required.")
    return value


def _form_bool(name: str) -> bool:
    return request.form.get(name) == "true"


def _form_optional_nullable_bool(name: str) -> bool | None:
    raw_value = request.form.get(name, "").strip().lower()
    if not raw_value:
        return None
    if raw_value == "true":
        return True
    if raw_value == "false":
        return False
    raise AdminFormError(f"{_field_label(name)} must be true or false.")


def _form_csv_list(name: str) -> list[str] | None:
    raw_value = request.form.get(name, "").strip()
    if not raw_value:
        return None
    values = [item.strip() for item in raw_value.split(",")]
    filtered = [item for item in values if item]
    return filtered or None


def _form_csv_float_list(name: str) -> list[float] | None:
    raw_value = request.form.get(name, "").strip()
    if not raw_value:
        return None
    converted: list[float] = []
    for item in raw_value.split(","):
        value = item.strip()
        if not value:
            continue
        try:
            converted.append(float(value))
        except ValueError:
            raise AdminFormError(f"{_field_label(name)} must contain only numbers.")
    return converted or None


def _optional_related_record(model: type[ModelT], form_key: str) -> ModelT | None:
    raw_value = request.form.get(form_key, "").strip()
    if not raw_value:
        return None
    try:
        record_id = int(raw_value)
    except ValueError:
        raise AdminFormError(f"{_field_label(form_key)} must be a valid integer.")
    record = db.session.get(model, record_id)
    if record is None:
        raise AdminFormError(f"{_field_label(form_key)} was not found.")
    return record


def _required_related_record(model: type[ModelT], form_key: str) -> ModelT:
    record = _optional_related_record(model, form_key)
    if record is None:
        raise AdminFormError(f"{_field_label(form_key)} is required.")
    return record


def _field_label(name: str) -> str:
    return name.replace("_", " ").strip().capitalize()
