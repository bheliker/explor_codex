from __future__ import annotations

from sqlalchemy import Select, select

from app.extensions import db
from app.models import PointOfInterest, User


def create_point_of_interest(
    *,
    owner: User | None = None,
    name: str,
    poi_type: str | None = None,
    subtype: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    url: str | None = None,
    description: str | None = None,
    icon: str | None = None,
) -> PointOfInterest:
    point_of_interest = PointOfInterest(
        owner=owner,
        name=name,
        type=poi_type,
        subtype=subtype,
        lat=lat,
        lon=lon,
        url=url,
        description=description,
        icon=icon,
    )
    db.session.add(point_of_interest)
    db.session.commit()
    return point_of_interest


def list_points_of_interest(*, owner: User | None = None) -> list[PointOfInterest]:
    statement: Select[tuple[PointOfInterest]] = select(PointOfInterest).order_by(PointOfInterest.id)
    if owner is not None:
        statement = statement.where(PointOfInterest.owner_id == owner.id)
    return list(db.session.scalars(statement))
