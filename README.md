# explor_codex

Plain Flask app template managed with `uv`.

## Requirements

- `uv`
- Python 3.13+

## Quick start

```bash
uv sync
docker compose up -d db
uv run flask --app 'app:create_app()' run --debug
```

The default local database URL targets the Dockerized PostGIS instance:

```bash
postgresql+psycopg://explor:explor@localhost:5432/explor
```

The app exposes:

- `/`
- `/health`
- `/admin/search`
- `/api/bootstrap/lookup-rows`
- `/api/search`
- `/api/search/reindex`
- `/api/groups`
- `/api/groups/<id>/memberships`
- `/api/groups/<id>/links`
- `/api/groups/<id>/dues`
- `/api/groups/<id>/routes`
- `/api/events`
- `/api/events/<id>/calendar-links`
- `/api/events/<id>/rsvps`
- `/api/events/<id>/fees`
- `/api/points-of-interest`
- `/api/images`
- `/api/routes`
- `/api/routes/<id>/links`
- `/api/routes/<id>/segments`
- `/api/segments`
- `/api/activities`

## Development checks

```bash
uv run ruff check .
uv run pytest
uv run mypy app tests
```

## Database

```bash
docker compose up -d db
uv run flask --app 'app:create_app()' db upgrade
```

Set `DATABASE_URL` to override the local default. Legacy `postgres://...` URLs are normalized
to `postgresql+psycopg://...` automatically.

Canonical lookup rows for RSVP statuses and group roles are seeded by migrations. If you ever
need to reassert them in an app context, use `app.bootstrap.ensure_canonical_lookup_rows()`.

## Services

Thin domain services now live in `app/services/` and provide a stable place for group and event
actions such as membership creation, RSVP updates, fee/link creation, point-of-interest creation,
and image creation. The JSON API routes in `app/routes.py` call into those services rather than
embedding business logic directly in Flask handlers. Routes, segments, activities, images, and
group-route linkage now follow the same thin service/API pattern.

Search now follows the same service-first approach. `app/services/search.py` maintains a portable
`search_document` index for groups, routes, segments, events, points of interest, and activities.
Use `POST /api/search/reindex` to rebuild the index and `GET /api/search?q=...&type=...&limit=...`
to query it. Search is intentionally app-level and cross-database for now; it does not depend on
Postgres `TSVECTOR` columns or GIN indexes.

There is also a thin server-rendered admin search console at `/admin/search`. It uses the same
search service layer and gives the project a lightweight HTML foothold without introducing a full
admin framework yet.

Routes, segments, and activities now carry `summary_polyline` and `full_track` geometry payloads.
POIs now also carry a `geoll` point geometry alongside their compatibility `lat` and `lon` fields.
These are wired for PostGIS on Postgres while remaining verification-friendly on SQLite.

## Project layout

```text
.
├── AGENTS.md
├── app/
│   ├── __init__.py
│   ├── auth.py
│   ├── bootstrap.py
│   ├── config.py
│   ├── extensions.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── activity.py
│   │   ├── calendar.py
│   │   ├── event.py
│   │   ├── event_fee.py
│   │   ├── group.py
│   │   ├── group_dues.py
│   │   ├── group_link.py
│   │   ├── lookup.py
│   │   ├── membership.py
│   │   ├── point_of_interest.py
│   │   ├── route.py
│   │   ├── search_document.py
│   │   ├── segment.py
│   │   └── user.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── activities.py
│   │   ├── events.py
│   │   ├── groups.py
│   │   ├── search.py
│   │   ├── points_of_interest.py
│   │   ├── routes.py
│   │   └── segments.py
│   └── routes.py
├── docker-compose.yml
├── migrations/
├── pyproject.toml
├── tests/
│   ├── conftest.py
│   └── test_app.py
└── README.md
```
