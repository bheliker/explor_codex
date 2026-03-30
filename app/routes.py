from __future__ import annotations

from http import HTTPStatus
from typing import Any, TypeVar, cast

from flask import Blueprint, abort, redirect, render_template, request, url_for
from sqlalchemy import func, select

from app.bootstrap import ensure_canonical_lookup_rows
from app.extensions import db
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
    update_event,
    update_group,
    update_route,
)

bp = Blueprint("core", __name__)
ModelT = TypeVar("ModelT")


@bp.get("/")
def index() -> tuple[dict[str, str], int]:
    return {"message": "explor_codex is ready"}, 200


@bp.get("/health")
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


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
        page_title=group.name or "Group",
        subtitle=group.shortname or group.primary_activity or group.type,
        tags=_combine_tags(
            group.tags, group.preference_tags, group.rider_classes, group.ride_classes
        ),
    )


@bp.route("/admin/groups/<int:group_id>/edit", methods=["GET", "POST"])
def admin_group_edit_route(group_id: int) -> str | Any:
    group = _get_or_404(Group, group_id)
    if request.method == "POST":
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
        return redirect(url_for("core.admin_group_detail_route", group_id=group.id))

    return render_template(
        "admin/edit.html",
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
        page_title=group.name or "Group",
    )


@bp.get("/admin/routes/<int:route_id>")
def admin_route_detail_route(route_id: int) -> str:
    route = _get_or_404(Route, route_id)
    return render_template(
        "admin/detail.html",
        detail_rows=_detail_rows(
            [
                ("Description", route.desc),
                ("Type", route.type),
                ("Subtype", route.subtype),
                ("Duration", route.duration),
                ("Length", route.length),
                ("Elevation gain", route.elevation_gain),
                ("Source", route.src),
                ("Source ID", route.src_id),
                ("Address", route.address),
                ("Linked groups", len(route.groups)),
                ("Linked segments", len(route.segments)),
            ]
        ),
        entity_id=route.id,
        entity_type_label="Route",
        edit_url=url_for("core.admin_route_edit_route", route_id=route.id),
        location=_join_location(route.city, route.state, route.country),
        page_title=route.name or "Route",
        subtitle=route.subtype or route.type,
        tags=route.tags,
    )


@bp.route("/admin/routes/<int:route_id>/edit", methods=["GET", "POST"])
def admin_route_edit_route(route_id: int) -> str | Any:
    route = _get_or_404(Route, route_id)
    if request.method == "POST":
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
        return redirect(url_for("core.admin_route_detail_route", route_id=route.id))

    return render_template(
        "admin/edit.html",
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
        page_title=route.name or "Route",
    )


@bp.get("/admin/segments/<int:segment_id>")
def admin_segment_detail_route(segment_id: int) -> str:
    segment = _get_or_404(Segment, segment_id)
    return render_template(
        "admin/detail.html",
        detail_rows=_detail_rows(
            [
                ("Description", segment.desc),
                ("Type", segment.type),
                ("Subtype", segment.subtype),
                ("Duration", segment.duration),
                ("Length", segment.length),
                ("Elevation gain", segment.elevation_gain),
                ("Grade", segment.grade),
                ("Rating", segment.rating),
                ("Source", segment.src),
                ("Source ID", segment.src_id),
                ("Linked routes", len(segment.routes)),
            ]
        ),
        entity_id=segment.id,
        entity_type_label="Segment",
        location=None,
        page_title=segment.name or "Segment",
        subtitle=segment.subtype or segment.type,
        tags=segment.tags,
    )


@bp.get("/admin/events/<int:event_id>")
def admin_event_detail_route(event_id: int) -> str:
    event = _get_or_404(Event, event_id)
    return render_template(
        "admin/detail.html",
        detail_rows=_detail_rows(
            [
                ("Description", event.description),
                ("Primary activity", event.primary_activity),
                ("Type", event.type),
                ("Subtype", event.subtype),
                ("Notes", event.notes),
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
        page_title=event.name or "Event",
        subtitle=event.subtype or event.type or event.primary_activity,
        tags=event.tags,
    )


@bp.route("/admin/events/<int:event_id>/edit", methods=["GET", "POST"])
def admin_event_edit_route(event_id: int) -> str | Any:
    event = _get_or_404(Event, event_id)
    if request.method == "POST":
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
        return redirect(url_for("core.admin_event_detail_route", event_id=event.id))

    return render_template(
        "admin/edit.html",
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
            _edit_text_field("route_id", "Route ID", event.route_id),
            _edit_text_field("activity_id", "Activity ID", event.activity_id),
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
        page_title=event.name or "Event",
    )


@bp.get("/admin/points-of-interest/<int:point_id>")
def admin_point_of_interest_detail_route(point_id: int) -> str:
    point = _get_or_404(PointOfInterest, point_id)
    return render_template(
        "admin/detail.html",
        detail_rows=_detail_rows(
            [
                ("Description", point.description),
                ("Type", point.type),
                ("Subtype", point.subtype),
                ("URL", point.url),
                ("Latitude", point.lat),
                ("Longitude", point.lon),
                ("Icon", point.icon),
                ("Images", len(point.images)),
            ]
        ),
        entity_id=point.id,
        entity_type_label="Point of Interest",
        location=None,
        page_title=point.name or "Point of Interest",
        subtitle=point.subtype or point.type,
        tags=point.tags,
    )


@bp.get("/admin/activities/<int:activity_id>")
def admin_activity_detail_route(activity_id: int) -> str:
    activity = _get_or_404(Activity, activity_id)
    return render_template(
        "admin/detail.html",
        detail_rows=_detail_rows(
            [
                ("Description", activity.desc),
                ("Type", activity.type),
                ("Subtype", activity.subtype),
                ("Duration", activity.duration),
                ("Length", activity.length),
                ("Elevation gain", activity.elevation_gain),
                ("Average speed", activity.average_speed),
                ("Max speed", activity.max_speed),
                ("Route ID", activity.route_id, _admin_detail_url("route", activity.route_id)),
                ("Photo URL", activity.photo_url),
                ("Images", len(activity.images)),
            ]
        ),
        entity_id=activity.id,
        entity_type_label="Activity",
        location=None,
        page_title=activity.name or "Activity",
        subtitle=activity.subtype or activity.type,
        tags=activity.tags,
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


def _admin_detail_url(entity_type: str, entity_id: int | None) -> str | None:
    if entity_id is None:
        return None

    endpoint_map = {
        "group": "core.admin_group_detail_route",
        "route": "core.admin_route_detail_route",
        "segment": "core.admin_segment_detail_route",
        "event": "core.admin_event_detail_route",
        "point_of_interest": "core.admin_point_of_interest_detail_route",
        "activity": "core.admin_activity_detail_route",
    }
    endpoint = endpoint_map.get(entity_type)
    if endpoint is None:
        return None

    if entity_type == "group":
        return url_for(endpoint, group_id=entity_id)
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
    raw_rows: list[tuple[str, object | None] | tuple[str, object | None, str | None]],
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


def _edit_text_field(name: str, label: str, value: object | None) -> dict[str, object]:
    return {"kind": "text", "label": label, "name": name, "value": _display_value(value) or ""}


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


def _display_value(value: object | None) -> str | None:
    if value is None:
        return None
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
        abort(HTTPStatus.BAD_REQUEST)
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
        abort(HTTPStatus.BAD_REQUEST)


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
    abort(HTTPStatus.BAD_REQUEST)


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
            abort(HTTPStatus.BAD_REQUEST)
    return converted or None


def _optional_related_record(model: type[ModelT], form_key: str) -> ModelT | None:
    raw_value = request.form.get(form_key, "").strip()
    if not raw_value:
        return None
    try:
        record_id = int(raw_value)
    except ValueError:
        abort(HTTPStatus.BAD_REQUEST)
    return _get_or_404(model, record_id)
