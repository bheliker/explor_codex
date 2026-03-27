from __future__ import annotations

from sqlalchemy import Select, select

from app.extensions import db
from app.models import Route, Segment


def create_segment(
    *,
    name: str,
    desc: str | None = None,
    duration: float | None = None,
    length: float | None = None,
    elevation_gain: float | None = None,
    elevation_loss: float | None = None,
    elev_high: float | None = None,
    elev_low: float | None = None,
    rating: float | None = None,
    grade: float | None = None,
    segment_type: str | None = None,
    subtype: str | None = None,
    src: str | None = None,
    src_id: str | None = None,
    src_url: str | None = None,
    start_latitude: float | None = None,
    start_longitude: float | None = None,
    end_latitude: float | None = None,
    end_longitude: float | None = None,
    track_hash: str | None = None,
    track_maxspeed: float | None = None,
) -> Segment:
    segment = Segment(
        name=name,
        desc=desc,
        duration=duration,
        length=length,
        elevation_gain=elevation_gain,
        elevation_loss=elevation_loss,
        elev_high=elev_high,
        elev_low=elev_low,
        rating=rating,
        grade=grade,
        type=segment_type,
        subtype=subtype,
        src=src,
        src_id=src_id,
        src_url=src_url,
        start_latitude=start_latitude,
        start_longitude=start_longitude,
        end_latitude=end_latitude,
        end_longitude=end_longitude,
        track_hash=track_hash,
        track_maxspeed=track_maxspeed,
    )
    db.session.add(segment)
    db.session.commit()
    return segment


def list_segments() -> list[Segment]:
    statement: Select[tuple[Segment]] = select(Segment).order_by(Segment.id)
    return list(db.session.scalars(statement))


def attach_segment_to_route(route: Route, segment: Segment) -> Route:
    if segment not in route.segments:
        route.segments.append(segment)
        db.session.commit()
    return route
