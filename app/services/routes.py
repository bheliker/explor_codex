from __future__ import annotations

from sqlalchemy import Select, select

from app.extensions import db
from app.models import Route, User


def create_route(
    *,
    creator: User | None = None,
    name: str,
    desc: str | None = None,
    private: bool | None = None,
    duration: float | None = None,
    length: float | None = None,
    elevation_gain: float | None = None,
    tags: list[str] | None = None,
    elevation_array: list[float] | None = None,
    route_type: str | None = None,
    subtype: str | None = None,
    src: str | None = None,
    src_id: str | None = None,
    start_latitude: float | None = None,
    start_longitude: float | None = None,
    end_latitude: float | None = None,
    end_longitude: float | None = None,
    summary_polyline: str | None = None,
    full_track: str | None = None,
    city: str | None = None,
    state: str | None = None,
    country: str | None = None,
    address: str | None = None,
    map_thumbnail: str | None = None,
) -> Route:
    route = Route(
        creator=creator,
        name=name,
        desc=desc,
        private=private,
        duration=duration,
        length=length,
        elevation_gain=elevation_gain,
        tags=tags,
        elevation_array=elevation_array,
        type=route_type,
        subtype=subtype,
        src=src,
        src_id=src_id,
        start_latitude=start_latitude,
        start_longitude=start_longitude,
        end_latitude=end_latitude,
        end_longitude=end_longitude,
        summary_polyline=summary_polyline,
        full_track=full_track,
        city=city,
        state=state,
        country=country,
        address=address,
        map_thumbnail=map_thumbnail,
    )
    db.session.add(route)
    db.session.commit()
    return route


def list_routes(*, creator: User | None = None) -> list[Route]:
    statement: Select[tuple[Route]] = select(Route).order_by(Route.id)
    if creator is not None:
        statement = statement.where(Route.creator_id == creator.id)
    return list(db.session.scalars(statement))
