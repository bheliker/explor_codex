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
- `/api/bootstrap/lookup-rows`
- `/api/groups`
- `/api/groups/<id>/memberships`
- `/api/groups/<id>/links`
- `/api/groups/<id>/dues`
- `/api/events`
- `/api/events/<id>/calendar-links`
- `/api/events/<id>/rsvps`
- `/api/events/<id>/fees`
- `/api/points-of-interest`
- `/api/routes`
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
actions such as membership creation, RSVP updates, fee/link creation, and point-of-interest
creation. The JSON API routes in `app/routes.py` call into those services rather than embedding
business logic directly in Flask handlers. Routes, segments, and activities now follow the same
thin service/API pattern.

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
│   │   ├── segment.py
│   │   └── user.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── activities.py
│   │   ├── events.py
│   │   ├── groups.py
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
