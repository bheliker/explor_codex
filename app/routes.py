from __future__ import annotations

from http import HTTPStatus
from typing import Any, TypeVar, cast

from flask import Blueprint, abort, request

from app.bootstrap import ensure_canonical_lookup_rows
from app.extensions import db
from app.models import (
    Calendar,
    Event,
    EventFee,
    EventInvitation,
    Group,
    GroupDues,
    GroupExternalUrl,
    Membership,
    PointOfInterest,
    Route,
    User,
)
from app.services import (
    add_event_fee,
    add_group_dues,
    add_group_link,
    attach_calendar,
    create_event,
    create_group,
    create_point_of_interest,
    create_route,
    ensure_group_membership,
    list_points_of_interest,
    list_routes,
    set_rsvp,
)

bp = Blueprint("core", __name__)
ModelT = TypeVar("ModelT")


@bp.get("/")
def index() -> tuple[dict[str, str], int]:
    return {"message": "explor_codex is ready"}, 200


@bp.get("/health")
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


@bp.post("/api/bootstrap/lookup-rows")
def bootstrap_lookup_rows() -> tuple[dict[str, list[str]], int]:
    return ensure_canonical_lookup_rows(), HTTPStatus.OK


@bp.post("/api/groups")
def create_group_route() -> tuple[dict[str, object], int]:
    payload = _json_payload()
    group = create_group(
        name=_required_str(payload, "name"),
        shortname=_required_str(payload, "shortname"),
        invite_only=_optional_bool(payload, "invite_only", default=False),
        private=_optional_bool(payload, "private", default=False),
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
    )
    return _group_dues_payload(group, dues), HTTPStatus.CREATED


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
        private=_optional_bool(payload, "private", default=False),
        description=_optional_str(payload, "description"),
        town=_optional_str(payload, "town"),
        state=_optional_str(payload, "state"),
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
    )
    return _event_fee_payload(event, fee), HTTPStatus.CREATED


@bp.get("/api/points-of-interest")
def list_points_of_interest_route() -> tuple[dict[str, object], int]:
    owner = None
    owner_id = request.args.get("owner_id", type=int)
    if owner_id is not None:
        owner = _get_or_404(User, owner_id)
    points = list_points_of_interest(owner=owner)
    return {"items": [_point_of_interest_payload(point) for point in points]}, HTTPStatus.OK


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
        url=_optional_str(payload, "url"),
        description=_optional_str(payload, "description"),
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
        route_type=_optional_str(payload, "type"),
        subtype=_optional_str(payload, "subtype"),
        src=_optional_str(payload, "src"),
        src_id=_optional_str(payload, "src_id"),
        start_latitude=_optional_float(payload, "start_latitude"),
        start_longitude=_optional_float(payload, "start_longitude"),
        end_latitude=_optional_float(payload, "end_latitude"),
        end_longitude=_optional_float(payload, "end_longitude"),
        city=_optional_str(payload, "city"),
        state=_optional_str(payload, "state"),
        country=_optional_str(payload, "country"),
        address=_optional_str(payload, "address"),
        map_thumbnail=_optional_str(payload, "map_thumbnail"),
    )
    return _route_payload(route), HTTPStatus.CREATED


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
        "url": link.url,
    }


def _group_dues_payload(group: Group, dues: GroupDues) -> dict[str, object]:
    return {
        "group_id": group.id,
        "dues_id": dues.id,
        "name": dues.name,
        "fee": dues.fee,
        "duration": dues.duration,
    }


def _event_payload(event: Event) -> dict[str, object]:
    return {
        "id": event.id,
        "name": event.name,
        "owner_id": event.owner_id,
        "private": event.private,
        "town": event.town,
        "state": event.state,
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
        "url": point.url,
        "description": point.description,
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
        "type": route.type,
        "subtype": route.subtype,
        "src": route.src,
        "src_id": route.src_id,
        "start_latitude": route.start_latitude,
        "start_longitude": route.start_longitude,
        "end_latitude": route.end_latitude,
        "end_longitude": route.end_longitude,
        "city": route.city,
        "state": route.state,
        "country": route.country,
        "address": route.address,
        "map_thumbnail": route.map_thumbnail,
    }
