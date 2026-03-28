from __future__ import annotations

import json
from typing import Any

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from shapely import to_geojson, to_wkt
from shapely.geometry import shape
from shapely.wkt import loads as load_wkt
from sqlalchemy import Text, func, select
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.orm import object_session
from sqlalchemy.sql.type_api import TypeEngine
from sqlalchemy.types import TypeDecorator


class GeometryType(TypeDecorator[object]):
    impl = Text
    cache_ok = True

    def __init__(self, geometry_type: str) -> None:
        super().__init__()
        self.geometry_type = geometry_type

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Geometry(self.geometry_type, srid=-1))
        return dialect.type_descriptor(Text())


def linestring_type() -> GeometryType:
    return GeometryType("LINESTRING")


def linestring_z_type() -> GeometryType:
    return GeometryType("LINESTRINGZ")


def to_storage_geometry(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.startswith("{"):
        return _geojson_text_to_wkt(stripped)
    return stripped


def to_api_geometry(instance: Any, attribute_name: str, value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return _wkt_to_geojson_text(value) if not value.lstrip().startswith("{") else value
    if isinstance(value, WKBElement):
        session = object_session(instance)
        if session is None or getattr(instance, "id", None) is None:
            return None
        model = type(instance)
        column = getattr(model, f"_{attribute_name}")
        statement = select(func.ST_AsGeoJSON(column)).where(model.id == instance.id)
        return session.scalar(statement)
    return str(value)


def _geojson_text_to_wkt(value: str) -> str:
    payload = json.loads(value)
    geometry_payload = payload["geometry"] if payload.get("type") == "Feature" else payload
    geometry = shape(geometry_payload)
    if geometry.geom_type != "LineString":
        raise ValueError("Only LineString geometry is supported")
    if geometry.is_empty:
        raise ValueError("LineString coordinates are required")
    return to_wkt(geometry, rounding_precision=-1)


def _wkt_to_geojson_text(value: str) -> str:
    geometry = load_wkt(value)
    if geometry.geom_type != "LineString":
        raise ValueError("Only LINESTRING WKT is supported")
    payload = json.loads(to_geojson(geometry))
    return json.dumps(_normalize_numbers(payload), separators=(",", ":"))


def _normalize_numbers(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_numbers(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value
