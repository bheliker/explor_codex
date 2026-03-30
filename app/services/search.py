from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, and_, case, delete, event, func, or_, select
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import Activity, Event, Group, PointOfInterest, Route, SearchDocument, Segment

SEARCHABLE_MODELS: tuple[type[Any], ...] = (Group, Route, Segment, Event, PointOfInterest, Activity)
SEARCHABLE_ENTITY_TYPES: tuple[str, ...] = (
    "group",
    "route",
    "segment",
    "event",
    "point_of_interest",
    "activity",
)
_SEARCH_LISTENERS_REGISTERED = False


def index_instance(instance: Any) -> SearchDocument | None:
    payload = _build_search_payload(instance)
    if payload is None:
        return None

    return _index_instance_for_session(session=db.session, payload=payload)


def rebuild_search_documents() -> int:
    db.session.execute(delete(SearchDocument))
    count = 0
    for model in SEARCHABLE_MODELS:
        for instance in db.session.scalars(select(model).order_by(model.id)):
            if index_instance(instance) is not None:
                count += 1
    db.session.commit()
    return count


def search_documents(
    *,
    query: str,
    types: Sequence[str] | None = None,
    limit: int = 25,
) -> list[SearchDocument]:
    tokens = _normalize_query_tokens(query)
    if not tokens:
        return []

    statement: Select[tuple[SearchDocument]] = select(SearchDocument)
    if types:
        statement = statement.where(SearchDocument.entity_type.in_(types))

    token_clauses = [func.lower(SearchDocument.search_text).like(f"%{token}%") for token in tokens]
    statement = statement.where(and_(*token_clauses))

    ranked_clauses = [
        SearchDocument.title.ilike(f"%{token}%") | SearchDocument.subtitle.ilike(f"%{token}%")
        for token in tokens
    ]
    statement = statement.order_by(
        case((or_(*ranked_clauses), 0), else_=1),
        SearchDocument.entity_type,
        SearchDocument.title,
        SearchDocument.entity_id,
    ).limit(limit)
    return list(db.session.scalars(statement))


def parse_search_types(raw_types: Iterable[str] | None) -> list[str]:
    if raw_types is None:
        return []

    parsed: list[str] = []
    for item in raw_types:
        normalized = item.strip().lower()
        if normalized and normalized in SEARCHABLE_ENTITY_TYPES and normalized not in parsed:
            parsed.append(normalized)
    return parsed


def register_search_listeners() -> None:
    global _SEARCH_LISTENERS_REGISTERED
    if _SEARCH_LISTENERS_REGISTERED:
        return

    event.listen(Session, "before_flush", _collect_search_changes)
    event.listen(Session, "after_flush_postexec", _apply_search_changes)
    _SEARCH_LISTENERS_REGISTERED = True


def _normalize_query_tokens(query: str) -> list[str]:
    parts = [part.strip().lower() for part in query.split()]
    return [part for part in parts if part]


def _build_search_payload(instance: Any) -> dict[str, Any] | None:
    if isinstance(instance, Group):
        return _group_payload(instance)
    if isinstance(instance, Route):
        return _route_payload(instance)
    if isinstance(instance, Segment):
        return _segment_payload(instance)
    if isinstance(instance, Event):
        return _event_payload(instance)
    if isinstance(instance, PointOfInterest):
        return _point_of_interest_payload(instance)
    if isinstance(instance, Activity):
        return _activity_payload(instance)
    return None


def _collect_search_changes(
    session: Session,
    flush_context: Any,  # noqa: ARG001
    instances: Any,  # noqa: ARG001
) -> None:
    upserts = [
        instance for instance in session.new.union(session.dirty) if _is_searchable(instance)
    ]
    deletes = [
        identity
        for instance in session.deleted
        if _is_searchable(instance)
        for identity in [_search_identity(instance)]
        if identity is not None
    ]

    if upserts:
        session.info["search_upserts"] = upserts
    if deletes:
        session.info["search_deletes"] = deletes


def _apply_search_changes(session: Session, flush_context: Any) -> None:  # noqa: ARG001
    upserts = session.info.pop("search_upserts", [])
    deletes = session.info.pop("search_deletes", [])

    for entity_type, entity_id in deletes:
        session.execute(
            delete(SearchDocument).where(
                SearchDocument.entity_type == entity_type,
                SearchDocument.entity_id == entity_id,
            )
        )

    for instance in upserts:
        if instance in session.deleted:
            continue
        payload = _build_search_payload(instance)
        if payload is not None:
            _index_instance_for_session(session=session, payload=payload)


def _index_instance_for_session(*, session: Any, payload: dict[str, Any]) -> SearchDocument:
    existing = session.scalar(
        select(SearchDocument).where(
            SearchDocument.entity_type == payload["entity_type"],
            SearchDocument.entity_id == payload["entity_id"],
        )
    )
    if existing is None:
        document = SearchDocument(**payload)
        session.add(document)
        return document

    existing.title = payload["title"]
    existing.subtitle = payload["subtitle"]
    existing.location = payload["location"]
    existing.tags = payload["tags"]
    existing.search_text = payload["search_text"]
    existing.updated_at = datetime.now(UTC)
    return existing


def _is_searchable(instance: Any) -> bool:
    return isinstance(instance, SEARCHABLE_MODELS)


def _search_identity(instance: Any) -> tuple[str, int] | None:
    payload = _build_search_payload(instance)
    if payload is None:
        return None
    return payload["entity_type"], payload["entity_id"]


def _group_payload(group: Group) -> dict[str, Any]:
    return _payload(
        entity_type="group",
        entity_id=group.id,
        title=group.name,
        subtitle=group.shortname or group.primary_activity or group.type,
        location=_join_parts(group.home_town, group.home_state, group.home_country),
        tags=_merge_tags(
            group.tags, group.preference_tags, group.rider_classes, group.ride_classes
        ),
        search_text_parts=[
            group.name,
            group.shortname,
            group.abbreviation,
            group.contact,
            group.about_blurb,
            group.more_info_url,
            group.group_type,
            group.category,
            group.primary_activity,
            group.type,
            group.subtype,
            group.home_town,
            group.home_state,
            group.home_country,
            group.full_address,
            *(group.tags or []),
            *(group.preference_tags or []),
            *(group.rider_classes or []),
            *(group.ride_classes or []),
        ],
    )


def _route_payload(route: Route) -> dict[str, Any]:
    return _payload(
        entity_type="route",
        entity_id=route.id,
        title=route.name,
        subtitle=route.subtype or route.type,
        location=_join_parts(route.city, route.state, route.country),
        tags=route.tags,
        search_text_parts=[
            route.name,
            route.desc,
            route.type,
            route.subtype,
            route.city,
            route.state,
            route.country,
            route.address,
            *(route.tags or []),
        ],
    )


def _segment_payload(segment: Segment) -> dict[str, Any]:
    return _payload(
        entity_type="segment",
        entity_id=segment.id,
        title=segment.name,
        subtitle=segment.subtype or segment.type,
        location=None,
        tags=segment.tags,
        search_text_parts=[
            segment.name,
            segment.desc,
            segment.type,
            segment.subtype,
            segment.src,
            segment.src_id,
            *(segment.tags or []),
        ],
    )


def _event_payload(event: Event) -> dict[str, Any]:
    return _payload(
        entity_type="event",
        entity_id=event.id,
        title=event.name,
        subtitle=event.subtype or event.type or event.primary_activity,
        location=_join_parts(event.town, event.state, event.country),
        tags=event.tags,
        search_text_parts=[
            event.name,
            event.description,
            event.primary_activity,
            event.type,
            event.subtype,
            event.notes,
            event.town,
            event.state,
            event.country,
            *(event.tags or []),
        ],
    )


def _point_of_interest_payload(point: PointOfInterest) -> dict[str, Any]:
    return _payload(
        entity_type="point_of_interest",
        entity_id=point.id,
        title=point.name,
        subtitle=point.subtype or point.type,
        location=None,
        tags=point.tags,
        search_text_parts=[
            point.name,
            point.description,
            point.type,
            point.subtype,
            point.icon,
            *(point.tags or []),
        ],
    )


def _activity_payload(activity: Activity) -> dict[str, Any]:
    return _payload(
        entity_type="activity",
        entity_id=activity.id,
        title=activity.name,
        subtitle=activity.subtype or activity.type,
        location=None,
        tags=activity.tags,
        search_text_parts=[
            activity.name,
            activity.desc,
            activity.type,
            activity.subtype,
            activity.src,
            activity.src_id,
            *(activity.tags or []),
        ],
    )


def _payload(
    *,
    entity_type: str,
    entity_id: int,
    title: str | None,
    subtitle: str | None,
    location: str | None,
    tags: list[str] | None,
    search_text_parts: Sequence[str | None],
) -> dict[str, Any]:
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "title": title,
        "subtitle": subtitle,
        "location": location,
        "tags": tags,
        "search_text": _normalize_search_text(search_text_parts),
    }


def _normalize_search_text(parts: Sequence[str | None]) -> str:
    normalized = [part.strip().lower() for part in parts if part and part.strip()]
    return " ".join(normalized)


def _join_parts(*parts: str | None) -> str | None:
    normalized = [part.strip() for part in parts if part and part.strip()]
    return ", ".join(normalized) if normalized else None


def _merge_tags(*groups: list[str] | None) -> list[str] | None:
    merged: list[str] = []
    for group in groups:
        if group is None:
            continue
        for tag in group:
            if tag not in merged:
                merged.append(tag)
    return merged or None
