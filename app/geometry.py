from __future__ import annotations

import json
from typing import Any

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from shapely import to_geojson, to_wkt
from shapely.geometry import MultiLineString, shape
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
    return GeometryType("GEOMETRY")


def linestring_z_type() -> GeometryType:
    return GeometryType("GEOMETRYZ")


def point_type() -> GeometryType:
    return GeometryType("POINT")


def to_storage_geometry(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.startswith("{"):
        return _geojson_text_to_wkt(stripped)
    return stripped


def to_storage_point_geometry(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.startswith("{"):
        return _geojson_text_to_point_wkt(stripped)
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


def to_api_point_geometry(instance: Any, attribute_name: str, value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return _point_wkt_to_geojson_text(value) if not value.lstrip().startswith("{") else value
    if isinstance(value, WKBElement):
        session = object_session(instance)
        if session is None or getattr(instance, "id", None) is None:
            return None
        model = type(instance)
        column = getattr(model, f"_{attribute_name}")
        statement = select(func.ST_AsGeoJSON(column)).where(model.id == instance.id)
        result = session.scalar(statement)
        return (
            json.dumps(_normalize_numbers(json.loads(result)), separators=(",", ":"))
            if result
            else None
        )
    return str(value)


def point_coordinates(value: str | None) -> tuple[float, float] | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    geometry = shape(json.loads(stripped)) if stripped.startswith("{") else load_wkt(stripped)
    if geometry.geom_type != "Point":
        raise ValueError("Only Point geometry is supported")
    x, y = geometry.coords[0]
    return float(x), float(y)


def _geojson_text_to_wkt(value: str) -> str:
    payload = json.loads(value)
    geometry = _lineal_geometry_from_payload(payload)
    return to_wkt(geometry, rounding_precision=-1)


def _geojson_text_to_point_wkt(value: str) -> str:
    payload = json.loads(value)
    geometry_payload = payload["geometry"] if payload.get("type") == "Feature" else payload
    geometry = shape(geometry_payload)
    if geometry.geom_type != "Point":
        raise ValueError("Only Point geometry is supported")
    if geometry.is_empty:
        raise ValueError("Point coordinates are required")
    return to_wkt(geometry, rounding_precision=-1)


def _wkt_to_geojson_text(value: str) -> str:
    geometry = load_wkt(value)
    allowed_types = ("LineString", "MultiLineString")
    if geometry.geom_type not in allowed_types:
        raise ValueError(f"Only {', '.join(allowed_types)} WKT is supported")
    payload = json.loads(to_geojson(geometry))
    return json.dumps(_normalize_numbers(payload), separators=(",", ":"))


def _point_wkt_to_geojson_text(value: str) -> str:
    geometry = load_wkt(value)
    if geometry.geom_type != "Point":
        raise ValueError("Only POINT WKT is supported")
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


def _lineal_geometry_from_payload(payload: Any) -> Any:
    payload_type = payload.get("type") if isinstance(payload, dict) else None
    if payload_type == "FeatureCollection":
        features = payload.get("features", [])
        if not isinstance(features, list) or not features:
            raise ValueError("FeatureCollection is empty")
        line_geometries: list[Any] = []
        for feature in features:
            line_geometries.extend(_line_components(_lineal_geometry_from_payload(feature)))
        return _merge_line_components(line_geometries)

    geometry_payload = payload["geometry"] if payload_type == "Feature" else payload
    geometry = shape(geometry_payload)
    allowed_types = ("LineString", "MultiLineString")
    if geometry.geom_type not in allowed_types:
        raise ValueError(f"Only {', '.join(allowed_types)} geometry is supported")
    if geometry.is_empty:
        raise ValueError(f"{geometry.geom_type} coordinates are required")
    return geometry


def _line_components(geometry: Any) -> list[Any]:
    if geometry.geom_type == "LineString":
        return [geometry]
    if geometry.geom_type == "MultiLineString":
        return list(geometry.geoms)
    raise ValueError(
        "Only LineString and MultiLineString geometry is supported, "
        f"got {geometry.geom_type}"
    )


def _merge_line_components(geometries: list[Any]) -> Any:
    if not geometries:
        raise ValueError("FeatureCollection is empty")
    if len(geometries) == 1:
        return geometries[0]
    return MultiLineString(geometries)
