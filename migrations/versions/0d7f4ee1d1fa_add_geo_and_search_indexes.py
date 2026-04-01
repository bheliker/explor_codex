"""add geo and search indexes

Revision ID: 0d7f4ee1d1fa
Revises: 9815df31c0ad
Create Date: 2026-04-01 11:15:00.000000

"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0d7f4ee1d1fa"
down_revision = "9815df31c0ad"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_search_document_updated_at", "search_document", ["updated_at"], unique=False
    )
    op.create_index("ix_calendar_group_id", "calendar", ["group_id"], unique=False)
    op.create_index("ix_route_creator_id", "route", ["creator_id"], unique=False)
    op.create_index("ix_activity_athlete_id", "activity", ["athlete_id"], unique=False)
    op.create_index("ix_activity_route_id", "activity", ["route_id"], unique=False)
    op.create_index("ix_event_owner_id", "event", ["owner_id"], unique=False)
    op.create_index("ix_event_route_id", "event", ["route_id"], unique=False)
    op.create_index("ix_event_activity_id", "event", ["activity_id"], unique=False)
    op.create_index("ix_event_date_start", "event", ["date_start"], unique=False)
    op.create_index("ix_group_admin_id", "group", ["admin_id"], unique=False)
    op.create_index("ix_group_hero_photo_id", "group", ["hero_photo_id"], unique=False)
    op.create_index("ix_group_external_url_group_id", "group_external_url", ["owner"], unique=False)
    op.create_index(
        "ix_group_external_url_route_id", "group_external_url", ["route_id"], unique=False
    )
    op.create_index("ix_group_dues_group_id", "group_dues", ["owner"], unique=False)
    op.create_index("ix_event_fee_event_id", "event_fee", ["event"], unique=False)
    op.create_index("ix_image_group_id", "image", ["group_id"], unique=False)
    op.create_index("ix_image_segment_id", "image", ["segment_id"], unique=False)
    op.create_index("ix_image_activity_id", "image", ["activity_id"], unique=False)
    op.create_index("ix_image_photographer_id", "image", ["photographer_id"], unique=False)
    op.create_index("ix_points_of_interest_owner", "points_of_interest", ["owner"], unique=False)
    op.create_index("ix_group_routes_route", "group_routes", ["route"], unique=False)
    op.create_index("ix_group_membership_members", "group_membership", ["members"], unique=False)
    op.create_index("ix_route_segments_segments", "route_segments", ["segments"], unique=False)
    op.create_index("ix_calendar_events_events", "calendar_events", ["events"], unique=False)
    op.create_index(
        "ix_event_attendance_attendance", "event_attendance", ["attendance"], unique=False
    )
    op.create_index("ix_event_images_image", "event_images", ["image"], unique=False)
    op.create_index("ix_poi_images_image", "poi_images", ["image"], unique=False)

    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute(
        """
        UPDATE image
        SET geoll = ST_SetSRID(
            ST_MakePoint(
                trim(split_part(latlng, ',', 2))::double precision,
                trim(split_part(latlng, ',', 1))::double precision
            ),
            -1
        )
        WHERE geoll IS NULL
          AND latlng IS NOT NULL
          AND trim(latlng) <> ''
          AND latlng ~ '^\\s*-?\\d+(\\.\\d+)?\\s*,\\s*-?\\d+(\\.\\d+)?\\s*$'
          AND NOT (
              trim(split_part(latlng, ',', 1))::double precision = 0
              AND trim(split_part(latlng, ',', 2))::double precision = 0
          )
        """
    )
    op.execute(
        """
        UPDATE event
        SET geoll = ST_SetSRID(ST_MakePoint(lon, lat), -1)
        WHERE geoll IS NULL
          AND lon IS NOT NULL
          AND lat IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE "group"
        SET geoll = ST_SetSRID(
            ST_MakePoint(
                trim(split_part(home_latlng, ',', 2))::double precision,
                trim(split_part(home_latlng, ',', 1))::double precision
            ),
            -1
        )
        WHERE geoll IS NULL
          AND home_latlng IS NOT NULL
          AND trim(home_latlng) <> ''
          AND home_latlng ~ '^\\s*-?\\d+(\\.\\d+)?\\s*,\\s*-?\\d+(\\.\\d+)?\\s*$'
          AND NOT (
              trim(split_part(home_latlng, ',', 1))::double precision = 0
              AND trim(split_part(home_latlng, ',', 2))::double precision = 0
          )
        """
    )

    op.execute(
        """
        CREATE INDEX ix_search_document_search_text_trgm
        ON search_document
        USING gin (lower(search_text) gin_trgm_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_group_geoll_gist
        ON "group"
        USING gist (geoll)
        WHERE geoll IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX ix_event_geoll_gist
        ON event
        USING gist (geoll)
        WHERE geoll IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX ix_points_of_interest_geoll_gist
        ON points_of_interest
        USING gist (geoll)
        WHERE geoll IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX ix_image_geoll_gist
        ON image
        USING gist (geoll)
        WHERE geoll IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX ix_route_summary_polyline_gist
        ON route
        USING gist (summary_polyline)
        WHERE summary_polyline IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX ix_segment_summary_polyline_gist
        ON segment
        USING gist (summary_polyline)
        WHERE summary_polyline IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX ix_activity_summary_polyline_gist
        ON activity
        USING gist (summary_polyline)
        WHERE summary_polyline IS NOT NULL
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_activity_summary_polyline_gist")
        op.execute("DROP INDEX IF EXISTS ix_segment_summary_polyline_gist")
        op.execute("DROP INDEX IF EXISTS ix_route_summary_polyline_gist")
        op.execute("DROP INDEX IF EXISTS ix_image_geoll_gist")
        op.execute("DROP INDEX IF EXISTS ix_points_of_interest_geoll_gist")
        op.execute("DROP INDEX IF EXISTS ix_event_geoll_gist")
        op.execute("DROP INDEX IF EXISTS ix_group_geoll_gist")
        op.execute("DROP INDEX IF EXISTS ix_search_document_search_text_trgm")

    op.drop_index("ix_poi_images_image", table_name="poi_images")
    op.drop_index("ix_event_images_image", table_name="event_images")
    op.drop_index("ix_event_attendance_attendance", table_name="event_attendance")
    op.drop_index("ix_calendar_events_events", table_name="calendar_events")
    op.drop_index("ix_route_segments_segments", table_name="route_segments")
    op.drop_index("ix_group_membership_members", table_name="group_membership")
    op.drop_index("ix_group_routes_route", table_name="group_routes")
    op.drop_index("ix_points_of_interest_owner", table_name="points_of_interest")
    op.drop_index("ix_image_photographer_id", table_name="image")
    op.drop_index("ix_image_activity_id", table_name="image")
    op.drop_index("ix_image_segment_id", table_name="image")
    op.drop_index("ix_image_group_id", table_name="image")
    op.drop_index("ix_event_fee_event_id", table_name="event_fee")
    op.drop_index("ix_group_dues_group_id", table_name="group_dues")
    op.drop_index("ix_group_external_url_route_id", table_name="group_external_url")
    op.drop_index("ix_group_external_url_group_id", table_name="group_external_url")
    op.drop_index("ix_group_hero_photo_id", table_name="group")
    op.drop_index("ix_group_admin_id", table_name="group")
    op.drop_index("ix_event_date_start", table_name="event")
    op.drop_index("ix_event_activity_id", table_name="event")
    op.drop_index("ix_event_route_id", table_name="event")
    op.drop_index("ix_event_owner_id", table_name="event")
    op.drop_index("ix_activity_route_id", table_name="activity")
    op.drop_index("ix_activity_athlete_id", table_name="activity")
    op.drop_index("ix_route_creator_id", table_name="route")
    op.drop_index("ix_calendar_group_id", table_name="calendar")
    op.drop_index("ix_search_document_updated_at", table_name="search_document")
