from __future__ import annotations

from sqlalchemy import Select, select

from app.extensions import db
from app.geometry import point_coordinates
from app.models import PointOfInterest, User


def create_point_of_interest(
    *,
    owner: User | None = None,
    name: str,
    poi_type: str | None = None,
    subtype: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    geoll: str | None = None,
    url: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    icon: str | None = None,
) -> PointOfInterest:
    if geoll is None and lat is not None and lon is not None:
        geoll = f'{{"type":"Point","coordinates":[{lon},{lat}]}}'
    if geoll is not None and (lat is None or lon is None):
        coordinates = point_coordinates(geoll)
        if coordinates is not None:
            lon, lat = coordinates

    point_of_interest = PointOfInterest(
        owner=owner,
        name=name,
        type=poi_type,
        subtype=subtype,
        lat=lat,
        lon=lon,
        geoll=geoll,
        url=url,
        description=description,
        tags=tags,
        icon=icon,
    )
    db.session.add(point_of_interest)
    db.session.commit()
    return point_of_interest


def update_point_of_interest(
    point_of_interest: PointOfInterest,
    *,
    name: str,
    poi_type: str | None = None,
    subtype: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    geoll: str | None = None,
    url: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    icon: str | None = None,
) -> PointOfInterest:
    if geoll is None and lat is not None and lon is not None:
        geoll = f'{{"type":"Point","coordinates":[{lon},{lat}]}}'
    if geoll is not None and (lat is None or lon is None):
        coordinates = point_coordinates(geoll)
        if coordinates is not None:
            lon, lat = coordinates

    point_of_interest.name = name
    point_of_interest.type = poi_type
    point_of_interest.subtype = subtype
    point_of_interest.lat = lat
    point_of_interest.lon = lon
    point_of_interest.geoll = geoll
    point_of_interest.url = url
    point_of_interest.description = description
    point_of_interest.tags = tags
    point_of_interest.icon = icon
    db.session.commit()
    return point_of_interest


def list_points_of_interest(*, owner: User | None = None) -> list[PointOfInterest]:
    statement: Select[tuple[PointOfInterest]] = select(PointOfInterest).order_by(PointOfInterest.id)
    if owner is not None:
        statement = statement.where(PointOfInterest.owner_id == owner.id)
    return list(db.session.scalars(statement))
