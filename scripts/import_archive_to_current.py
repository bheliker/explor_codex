from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_SOURCE_DSN = "postgresql://explor:explor@localhost:5432/explor_archive"
DEFAULT_TARGET_DSN = "postgresql://explor:explor@localhost:5432/explor"
DEFAULT_BATCH_SIZE = 1000

ROLE_NAME_MAP = {
    "admin": "admin",
    "member": "member",
    "pending": "pending",
    "lead": "admin",
    "invited": "pending",
}

EVENT_STATUS_NAME_MAP = {
    "invited": "invited",
    "attending": "attending",
    "interested": "interested",
    "not_attending": "not_attending",
}


RowAdapter = Callable[[dict[str, Any]], Sequence[Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import archived Explor data into the current local schema."
    )
    parser.add_argument("--source-dsn", default=DEFAULT_SOURCE_DSN)
    parser.add_argument("--target-dsn", default=DEFAULT_TARGET_DSN)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--skip-images",
        action="store_true",
        help="Skip importing images and event image links on the first pass.",
    )
    parser.add_argument(
        "--skip-search-rebuild",
        action="store_true",
        help="Skip rebuilding search_document after the import finishes.",
    )
    return parser.parse_args()


def now_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def as_jsonb(value: Any) -> Jsonb | None:
    if value is None:
        return None
    return Jsonb(value)


def list_or_none(value: Any) -> list[Any] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def ensure_text(value: str | None, fallback: str) -> str:
    if value is None or not value.strip():
        return fallback
    return value


def ensure_password_hash(value: str | None, *, user_id: int) -> str:
    if value:
        return value
    return generate_password_hash(f"archived-user-{user_id}")


def read_lookup_map(connection: psycopg.Connection[Any], table_name: str) -> dict[str, int]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(f"SELECT id, name FROM {table_name} ORDER BY id")
        return {row["name"].lower(): row["id"] for row in cursor.fetchall()}


def ensure_lookup_rows(target_dsn: str) -> None:
    os.environ["DATABASE_URL"] = target_dsn
    from app import create_app
    from app.bootstrap import ensure_canonical_lookup_rows

    app = create_app()
    with app.app_context():
        ensure_canonical_lookup_rows()


def copy_rows(
    *,
    source: psycopg.Connection[Any],
    target: psycopg.Connection[Any],
    label: str,
    select_sql: str,
    insert_sql: str,
    row_adapter: RowAdapter,
    batch_size: int,
) -> int:
    inserted = 0
    with source.cursor(row_factory=dict_row) as source_cursor, target.cursor() as target_cursor:
        source_cursor.execute(select_sql)
        while rows := source_cursor.fetchmany(batch_size):
            adapted_rows = [row_adapter(row) for row in rows]
            target_cursor.executemany(insert_sql, adapted_rows)
            inserted += len(adapted_rows)
            print(f"{label}: imported {inserted}")
    return inserted


def copy_bridge_rows(
    *,
    source: psycopg.Connection[Any],
    target: psycopg.Connection[Any],
    label: str,
    select_sql: str,
    batch_size: int,
) -> int:
    inserted = 0
    with source.cursor() as source_cursor, target.cursor() as target_cursor:
        source_cursor.execute(select_sql)
        while rows := source_cursor.fetchmany(batch_size):
            target_cursor.executemany(
                f"INSERT INTO {label} VALUES (%s, %s) ON CONFLICT DO NOTHING",
                rows,
            )
            inserted += len(rows)
            print(f"{label}: imported {inserted}")
    return inserted


def reset_sequences(target: psycopg.Connection[Any], table_names: Iterable[str]) -> None:
    statements = []
    for table_name in table_names:
        statements.append(
            f"""
            SELECT setval(
                pg_get_serial_sequence('public.{table_name}', 'id'),
                COALESCE((SELECT MAX(id) FROM public.{table_name}), 1),
                (SELECT MAX(id) IS NOT NULL FROM public.{table_name})
            );
            """
        )
    with target.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)


def rebuild_search_documents(target_dsn: str) -> int:
    os.environ["DATABASE_URL"] = target_dsn
    from app import create_app
    from app.services.search import rebuild_search_documents

    app = create_app()
    with app.app_context():
        return rebuild_search_documents()


def import_archive(
    *,
    source_dsn: str,
    target_dsn: str,
    batch_size: int,
    skip_images: bool,
    skip_search_rebuild: bool,
) -> None:
    ensure_lookup_rows(target_dsn)

    with psycopg.connect(source_dsn) as source, psycopg.connect(target_dsn) as target:
        source.autocommit = False
        target.autocommit = False

        target_role_map = read_lookup_map(target, "group_role")
        target_event_status_map = read_lookup_map(target, "event_invitation_status")

        imported_counts: dict[str, int] = {}
        current_time = now_utc()

        imported_counts["user"] = copy_rows(
            source=source,
            target=target,
            label="user",
            select_sql="""
                SELECT
                    id,
                    username,
                    email,
                    password_hash,
                    firstname,
                    lastname,
                    account_type,
                    preference_tags,
                    tags,
                    home_town,
                    home_state,
                    home_country,
                    home_gym,
                    home_latlng,
                    ST_AsEWKT(geoll) AS geoll,
                    active,
                    init_date,
                    update_date,
                    last_login_at
                FROM public."user"
                ORDER BY id
            """,
            insert_sql="""
                INSERT INTO public."user" (
                    id,
                    username,
                    email,
                    password_hash,
                    firstname,
                    lastname,
                    account_type,
                    preference_tags,
                    tags,
                    home_town,
                    home_state,
                    home_country,
                    home_gym,
                    home_latlng,
                    geoll,
                    active,
                    site_admin,
                    init_date,
                    update_date,
                    last_login_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, ST_GeomFromEWKT(%s), %s, %s, %s, %s, %s
                )
            """,
            row_adapter=lambda row: (
                row["id"],
                ensure_text(row["username"], f"archived-user-{row['id']}"),
                ensure_text(row["email"], f"archived-user-{row['id']}@explor.local"),
                ensure_password_hash(row["password_hash"], user_id=row["id"]),
                row["firstname"],
                row["lastname"],
                row["account_type"],
                as_jsonb(list_or_none(row["preference_tags"])),
                as_jsonb(list_or_none(row["tags"])),
                row["home_town"],
                row["home_state"],
                row["home_country"],
                row["home_gym"],
                row["home_latlng"],
                row["geoll"],
                True if row["active"] is None else row["active"],
                False,
                row["init_date"] or current_time,
                row["update_date"] or current_time,
                row["last_login_at"],
            ),
            batch_size=batch_size,
        )

        imported_counts["route"] = copy_rows(
            source=source,
            target=target,
            label="route",
            select_sql="""
                SELECT
                    id,
                    init_date,
                    update_date,
                    name,
                    "desc",
                    athlete_id,
                    creator_id,
                    private,
                    duration,
                    length,
                    elevation_gain,
                    tags,
                    elevation_array,
                    type,
                    subtype,
                    grade,
                    rating,
                    src,
                    src_id,
                    start_longitude,
                    start_latitude,
                    end_longitude,
                    end_latitude,
                    ST_AsEWKT(summary_polyline) AS summary_polyline,
                    ST_AsEWKT(full_track) AS full_track,
                    map_thumbnail,
                    city,
                    state,
                    country,
                    address
                FROM public.route
                ORDER BY id
            """,
            insert_sql="""
                INSERT INTO public.route (
                    id,
                    init_date,
                    update_date,
                    name,
                    "desc",
                    athlete_id,
                    creator_id,
                    private,
                    duration,
                    length,
                    elevation_gain,
                    tags,
                    elevation_array,
                    type,
                    subtype,
                    grade,
                    rating,
                    src,
                    src_id,
                    start_longitude,
                    start_latitude,
                    end_longitude,
                    end_latitude,
                    summary_polyline,
                    full_track,
                    map_thumbnail,
                    city,
                    state,
                    country,
                    address
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, ST_GeomFromEWKT(%s), ST_GeomFromEWKT(%s), %s,
                    %s, %s, %s, %s
                )
            """,
            row_adapter=lambda row: (
                row["id"],
                row["init_date"] or current_time,
                row["update_date"] or current_time,
                row["name"],
                row["desc"],
                row["athlete_id"],
                row["creator_id"],
                row["private"],
                row["duration"],
                row["length"],
                row["elevation_gain"],
                as_jsonb(list_or_none(row["tags"])),
                as_jsonb(list_or_none(row["elevation_array"])),
                row["type"],
                row["subtype"],
                row["grade"],
                row["rating"],
                row["src"],
                row["src_id"],
                row["start_longitude"],
                row["start_latitude"],
                row["end_longitude"],
                row["end_latitude"],
                row["summary_polyline"],
                row["full_track"],
                row["map_thumbnail"],
                row["city"],
                row["state"],
                row["country"],
                row["address"],
            ),
            batch_size=batch_size,
        )

        imported_counts["segment"] = copy_rows(
            source=source,
            target=target,
            label="segment",
            select_sql="""
                SELECT
                    id,
                    init_date,
                    update_date,
                    name,
                    "desc",
                    duration,
                    length,
                    elevation_gain,
                    elevation_array,
                    elevation_loss,
                    elev_high,
                    elev_low,
                    rating,
                    grade,
                    type,
                    subtype,
                    tags,
                    src,
                    src_id,
                    src_url,
                    start_longitude,
                    start_latitude,
                    end_longitude,
                    end_latitude,
                    ST_AsEWKT(summary_polyline) AS summary_polyline,
                    ST_AsEWKT(full_track) AS full_track,
                    track_hash,
                    track_maxspeed,
                    record_date
                FROM public.segment
                ORDER BY id
            """,
            insert_sql="""
                INSERT INTO public.segment (
                    id,
                    init_date,
                    update_date,
                    name,
                    "desc",
                    duration,
                    length,
                    elevation_gain,
                    elevation_array,
                    elevation_loss,
                    elev_high,
                    elev_low,
                    rating,
                    grade,
                    type,
                    subtype,
                    tags,
                    src,
                    src_id,
                    src_url,
                    start_longitude,
                    start_latitude,
                    end_longitude,
                    end_latitude,
                    summary_polyline,
                    full_track,
                    track_hash,
                    track_maxspeed,
                    record_date
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, ST_GeomFromEWKT(%s), ST_GeomFromEWKT(%s),
                    %s, %s, %s
                )
            """,
            row_adapter=lambda row: (
                row["id"],
                row["init_date"] or current_time,
                row["update_date"] or current_time,
                row["name"],
                row["desc"],
                row["duration"],
                row["length"],
                row["elevation_gain"],
                as_jsonb(list_or_none(row["elevation_array"])),
                row["elevation_loss"],
                row["elev_high"],
                row["elev_low"],
                row["rating"],
                row["grade"],
                row["type"],
                row["subtype"],
                as_jsonb(list_or_none(row["tags"])),
                row["src"],
                row["src_id"],
                row["src_url"],
                row["start_longitude"],
                row["start_latitude"],
                row["end_longitude"],
                row["end_latitude"],
                row["summary_polyline"],
                row["full_track"],
                row["track_hash"],
                row["track_maxspeed"],
                row["record_date"] or current_time,
            ),
            batch_size=batch_size,
        )

        imported_counts["group"] = copy_rows(
            source=source,
            target=target,
            label="group",
            select_sql="""
                SELECT
                    id,
                    name,
                    shortname,
                    abbreviation,
                    contact,
                    contact_sec,
                    about_blurb,
                    more_info_url,
                    private,
                    invite_only,
                    active,
                    verified,
                    init_date,
                    update_date,
                    membership_level,
                    account_type,
                    group_type,
                    category,
                    primary_activity,
                    type,
                    subtype,
                    date_founded,
                    dues,
                    waiver_url,
                    waiver_date,
                    logo,
                    profile_photo,
                    hero_video,
                    home_town,
                    home_state,
                    home_country,
                    home_latlng,
                    home_add,
                    full_address,
                    admin_id,
                    ST_AsEWKT(geoll) AS geoll,
                    preference_tags,
                    tags,
                    rider_classes,
                    ride_classes
                FROM public."group"
                ORDER BY id
            """,
            insert_sql="""
                INSERT INTO public."group" (
                    id,
                    name,
                    shortname,
                    abbreviation,
                    contact,
                    contact_sec,
                    about_blurb,
                    more_info_url,
                    private,
                    invite_only,
                    active,
                    verified,
                    init_date,
                    update_date,
                    membership_level,
                    account_type,
                    group_type,
                    category,
                    primary_activity,
                    type,
                    subtype,
                    date_founded,
                    dues,
                    waiver_url,
                    waiver_date,
                    logo,
                    profile_photo,
                    hero_video,
                    home_town,
                    home_state,
                    home_country,
                    home_latlng,
                    home_add,
                    full_address,
                    admin_id,
                    geoll,
                    hero_photo_id,
                    preference_tags,
                    tags,
                    rider_classes,
                    ride_classes
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, ST_GeomFromEWKT(%s), %s, %s, %s, %s, %s
                )
            """,
            row_adapter=lambda row: (
                row["id"],
                ensure_text(row["name"], f"Archived Group {row['id']}"),
                row["shortname"],
                row["abbreviation"],
                row["contact"],
                row["contact_sec"],
                row["about_blurb"],
                row["more_info_url"],
                False if row["private"] is None else row["private"],
                False if row["invite_only"] is None else row["invite_only"],
                True if row["active"] is None else row["active"],
                row["verified"],
                row["init_date"] or current_time,
                row["update_date"] or current_time,
                row["membership_level"],
                row["account_type"],
                row["group_type"],
                row["category"],
                row["primary_activity"],
                row["type"],
                row["subtype"],
                row["date_founded"],
                row["dues"],
                row["waiver_url"],
                row["waiver_date"],
                row["logo"],
                row["profile_photo"],
                row["hero_video"],
                row["home_town"],
                row["home_state"],
                row["home_country"],
                row["home_latlng"],
                row["home_add"],
                row["full_address"],
                row["admin_id"],
                row["geoll"],
                None,
                as_jsonb(list_or_none(row["preference_tags"])),
                as_jsonb(list_or_none(row["tags"])),
                as_jsonb(list_or_none(row["rider_classes"])),
                as_jsonb(list_or_none(row["ride_classes"])),
            ),
            batch_size=batch_size,
        )

        imported_counts["calendar"] = copy_rows(
            source=source,
            target=target,
            label="calendar",
            select_sql="""
                SELECT
                    id,
                    name,
                    description,
                    private,
                    owner,
                    group_id,
                    tags,
                    date_created,
                    date_updated,
                    primary_activity,
                    type,
                    subtype,
                    url,
                    photo_url,
                    logo,
                    profile_photo,
                    notes
                FROM public.calendar
                ORDER BY id
            """,
            insert_sql="""
                INSERT INTO public.calendar (
                    id,
                    name,
                    description,
                    private,
                    owner,
                    group_id,
                    tags,
                    date_created,
                    date_updated,
                    primary_activity,
                    type,
                    subtype,
                    url,
                    photo_url,
                    logo,
                    profile_photo,
                    notes
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """,
            row_adapter=lambda row: (
                row["id"],
                row["name"],
                row["description"],
                False if row["private"] is None else row["private"],
                row["owner"],
                row["group_id"],
                as_jsonb(list_or_none(row["tags"])),
                row["date_created"] or current_time,
                row["date_updated"] or current_time,
                row["primary_activity"],
                row["type"],
                row["subtype"],
                row["url"],
                row["photo_url"],
                row["logo"],
                row["profile_photo"],
                row["notes"],
            ),
            batch_size=batch_size,
        )

        imported_counts["event"] = copy_rows(
            source=source,
            target=target,
            label="event",
            select_sql="""
                SELECT
                    id,
                    name,
                    description,
                    private,
                    owner,
                    email,
                    date_start,
                    date_end,
                    date_created,
                    date_updated,
                    duration,
                    primary_activity,
                    type,
                    subtype,
                    url,
                    reg_url,
                    photo_url,
                    logo,
                    profile_photo,
                    notes,
                    lon,
                    lat,
                    town,
                    state,
                    country,
                    latlng,
                    route_id,
                    activity_id,
                    ST_AsEWKT(geoll) AS geoll,
                    tags
                FROM public.event
                ORDER BY id
            """,
            insert_sql="""
                INSERT INTO public.event (
                    id,
                    name,
                    description,
                    private,
                    owner_id,
                    email,
                    date_start,
                    date_end,
                    date_created,
                    date_updated,
                    duration,
                    primary_activity,
                    type,
                    subtype,
                    url,
                    reg_url,
                    photo_url,
                    logo,
                    profile_photo,
                    notes,
                    lon,
                    lat,
                    town,
                    state,
                    country,
                    latlng,
                    route_id,
                    activity_id,
                    geoll,
                    tags
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, ST_GeomFromEWKT(%s), %s
                )
            """,
            row_adapter=lambda row: (
                row["id"],
                row["name"],
                row["description"],
                False if row["private"] is None else row["private"],
                row["owner"],
                row["email"],
                row["date_start"] or current_time,
                row["date_end"],
                row["date_created"] or current_time,
                row["date_updated"] or current_time,
                row["duration"],
                row["primary_activity"],
                row["type"],
                row["subtype"],
                row["url"],
                row["reg_url"],
                row["photo_url"],
                row["logo"],
                row["profile_photo"],
                row["notes"],
                row["lon"],
                row["lat"],
                row["town"],
                row["state"],
                row["country"],
                row["latlng"],
                row["route_id"],
                row["activity_id"],
                row["geoll"],
                as_jsonb(list_or_none(row["tags"])),
            ),
            batch_size=batch_size,
        )

        imported_counts["group_dues"] = copy_rows(
            source=source,
            target=target,
            label="group_dues",
            select_sql="""
                SELECT id, owner, fee, name, description, duration, tags
                FROM public.group_dues
                ORDER BY id
            """,
            insert_sql="""
                INSERT INTO public.group_dues (
                    id, owner, fee, name, description, duration, tags
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            row_adapter=lambda row: (
                row["id"],
                row["owner"],
                row["fee"],
                row["name"],
                row["description"],
                row["duration"],
                as_jsonb(list_or_none(row["tags"])),
            ),
            batch_size=batch_size,
        )

        imported_counts["group_external_url"] = copy_rows(
            source=source,
            target=target,
            label="group_external_url",
            select_sql="""
                SELECT
                    id,
                    url,
                    owner,
                    route_id,
                    date_created,
                    date_updated,
                    type,
                    subtype,
                    name,
                    description,
                    tags,
                    icon,
                    img
                FROM public.external_urls
                ORDER BY id
            """,
            insert_sql="""
                INSERT INTO public.group_external_url (
                    id,
                    url,
                    owner,
                    route_id,
                    date_created,
                    date_updated,
                    type,
                    subtype,
                    name,
                    description,
                    tags,
                    icon,
                    img
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """,
            row_adapter=lambda row: (
                row["id"],
                row["url"],
                row["owner"],
                row["route_id"],
                row["date_created"] or current_time,
                row["date_updated"] or current_time,
                row["type"],
                row["subtype"],
                row["name"],
                row["description"],
                as_jsonb(list_or_none(row["tags"])),
                row["icon"],
                row["img"],
            ),
            batch_size=batch_size,
        )

        imported_counts["membership"] = copy_rows(
            source=source,
            target=target,
            label="membership",
            select_sql="""
                SELECT
                    m.id,
                    m.user_id,
                    lower(gr.name) AS role_name,
                    m.join_date,
                    m.dues_paid_date,
                    m.waiver_date
                FROM public.membership AS m
                JOIN public.group_role AS gr ON gr.id = m.role_id
                ORDER BY m.id
            """,
            insert_sql="""
                INSERT INTO public.membership (
                    id,
                    user_id,
                    role_id,
                    join_date,
                    dues_paid_date,
                    waiver_date
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            row_adapter=lambda row: (
                row["id"],
                row["user_id"],
                target_role_map[ROLE_NAME_MAP[row["role_name"]]],
                row["join_date"] or current_time,
                row["dues_paid_date"],
                row["waiver_date"],
            ),
            batch_size=batch_size,
        )

        imported_counts["event_invitation"] = copy_rows(
            source=source,
            target=target,
            label="event_invitation",
            select_sql="""
                SELECT
                    ei.id,
                    ei.user_id,
                    lower(eis.name) AS status_name,
                    ei.rsvp_date,
                    ei.fee_paid_date,
                    ei.waiver_date
                FROM public.event_invitation AS ei
                JOIN public.event_invitation_status AS eis ON eis.id = ei.status_id
                ORDER BY ei.id
            """,
            insert_sql="""
                INSERT INTO public.event_invitation (
                    id,
                    user_id,
                    status_id,
                    rsvp_date,
                    fee_paid_date,
                    waiver_date
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            row_adapter=lambda row: (
                row["id"],
                row["user_id"],
                target_event_status_map[EVENT_STATUS_NAME_MAP[row["status_name"]]],
                row["rsvp_date"] or current_time,
                row["fee_paid_date"],
                row["waiver_date"],
            ),
            batch_size=batch_size,
        )

        if not skip_images:
            imported_counts["image"] = copy_rows(
                source=source,
                target=target,
                label="image",
                select_sql="""
                    SELECT
                        id,
                        img_small,
                        img_medium,
                        img_large,
                        img_thumb,
                        alt_txt,
                        title,
                        caption,
                        date,
                        group_id,
                        segment_id,
                        activity_id,
                        photographer_id,
                        latlng,
                        ST_AsEWKT(geoll) AS geoll,
                        tags,
                        url
                    FROM public.image
                    ORDER BY id
                """,
                insert_sql="""
                    INSERT INTO public.image (
                        id,
                        img_small,
                        img_medium,
                        img_large,
                        img_thumb,
                        alt_txt,
                        title,
                        caption,
                        date,
                        group_id,
                        segment_id,
                        activity_id,
                        photographer_id,
                        latlng,
                        geoll,
                        tags,
                        url
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, ST_GeomFromEWKT(%s), %s, %s
                    )
                """,
                row_adapter=lambda row: (
                    row["id"],
                    row["img_small"],
                    row["img_medium"],
                    row["img_large"],
                    row["img_thumb"],
                    row["alt_txt"],
                    row["title"],
                    row["caption"],
                    row["date"] or current_time,
                    row["group_id"],
                    row["segment_id"],
                    row["activity_id"],
                    row["photographer_id"],
                    row["latlng"],
                    row["geoll"],
                    as_jsonb(list_or_none(row["tags"])),
                    row["url"],
                ),
                batch_size=batch_size,
            )

        imported_counts["group_membership"] = copy_bridge_rows(
            source=source,
            target=target,
            label="public.group_membership",
            select_sql=(
                "SELECT groups, members "
                "FROM public.group_membership "
                "ORDER BY groups, members"
            ),
            batch_size=batch_size,
        )
        imported_counts["group_routes"] = copy_bridge_rows(
            source=source,
            target=target,
            label="public.group_routes",
            select_sql='SELECT "group", route FROM public.group_routes ORDER BY "group", route',
            batch_size=batch_size,
        )
        imported_counts["route_segments"] = copy_bridge_rows(
            source=source,
            target=target,
            label="public.route_segments",
            select_sql=(
                "SELECT routes, segments "
                "FROM public.route_segments "
                "ORDER BY routes, segments"
            ),
            batch_size=batch_size,
        )
        imported_counts["calendar_events"] = copy_bridge_rows(
            source=source,
            target=target,
            label="public.calendar_events",
            select_sql=(
                "SELECT calendars, events "
                "FROM public.calendar_events "
                "ORDER BY calendars, events"
            ),
            batch_size=batch_size,
        )
        imported_counts["event_attendance"] = copy_bridge_rows(
            source=source,
            target=target,
            label="public.event_attendance",
            select_sql=(
                "SELECT events, attendance "
                "FROM public.event_attendance "
                "ORDER BY events, attendance"
            ),
            batch_size=batch_size,
        )

        if not skip_images:
            imported_counts["event_images"] = copy_bridge_rows(
                source=source,
                target=target,
                label="public.event_images",
                select_sql="""
                    SELECT event, image FROM public.event_images
                    UNION
                    SELECT event_id AS event, id AS image
                    FROM public.image
                    WHERE event_id IS NOT NULL
                    ORDER BY 1, 2
                """,
                batch_size=batch_size,
            )

        reset_sequences(
            target,
            [
                '"user"',
                "route",
                "segment",
                '"group"',
                "calendar",
                "event",
                "group_dues",
                "group_external_url",
                "membership",
                "event_invitation",
                "image",
            ],
        )
        target.commit()

    if not skip_search_rebuild:
        rebuilt = rebuild_search_documents(target_dsn)
        imported_counts["search_document"] = rebuilt

    print("Import complete.")
    for table_name, count in imported_counts.items():
        print(f"{table_name}: {count}")


def main() -> None:
    args = parse_args()
    import_archive(
        source_dsn=args.source_dsn,
        target_dsn=args.target_dsn,
        batch_size=args.batch_size,
        skip_images=args.skip_images,
        skip_search_rebuild=args.skip_search_rebuild,
    )


if __name__ == "__main__":
    main()
