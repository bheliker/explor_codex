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

## Project layout

```text
.
├── AGENTS.md
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── extensions.py
│   ├── models/
│   │   └── __init__.py
│   └── routes.py
├── docker-compose.yml
├── pyproject.toml
├── tests/
│   ├── conftest.py
│   └── test_app.py
└── README.md
```
