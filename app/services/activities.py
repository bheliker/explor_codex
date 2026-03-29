from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Select, select

from app.extensions import db
from app.models import Activity, Route, User
from app.services.search import index_instance


def create_activity(
    *,
    athlete: User | None = None,
    route: Route | None = None,
    name: str,
    desc: str | None = None,
    private: bool | None = None,
    photo_url: str | None = None,
    tags: list[str] | None = None,
    duration: float | None = None,
    length: float | None = None,
    elevation_gain: float | None = None,
    average_speed: float | None = None,
    max_speed: float | None = None,
    moving_time: float | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    total_elevation_gain: float | None = None,
    elev_high: float | None = None,
    elev_low: float | None = None,
    activity_type: str | None = None,
    subtype: str | None = None,
    src: str | None = None,
    src_id: str | None = None,
    start_latitude: float | None = None,
    start_longitude: float | None = None,
    end_latitude: float | None = None,
    end_longitude: float | None = None,
    summary_polyline: str | None = None,
    full_track: str | None = None,
) -> Activity:
    activity = Activity(
        athlete=athlete,
        route=route,
        name=name,
        desc=desc,
        private=private,
        photo_url=photo_url,
        tags=tags,
        duration=duration,
        length=length,
        elevation_gain=elevation_gain,
        average_speed=average_speed,
        max_speed=max_speed,
        moving_time=moving_time,
        start_date=start_date or datetime.now(UTC),
        end_date=end_date or datetime.now(UTC),
        total_elevation_gain=total_elevation_gain,
        elev_high=elev_high,
        elev_low=elev_low,
        type=activity_type,
        subtype=subtype,
        src=src,
        src_id=src_id,
        start_latitude=start_latitude,
        start_longitude=start_longitude,
        end_latitude=end_latitude,
        end_longitude=end_longitude,
        summary_polyline=summary_polyline,
        full_track=full_track,
    )
    db.session.add(activity)
    db.session.flush()
    index_instance(activity)
    db.session.commit()
    return activity


def list_activities(*, athlete: User | None = None, route: Route | None = None) -> list[Activity]:
    statement: Select[tuple[Activity]] = select(Activity).order_by(Activity.id)
    if athlete is not None:
        statement = statement.where(Activity.athlete_id == athlete.id)
    if route is not None:
        statement = statement.where(Activity.route_id == route.id)
    return list(db.session.scalars(statement))
