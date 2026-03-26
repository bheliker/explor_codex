# explor_codex

Plain Flask app template managed with `uv`.

## Requirements

- `uv`
- Python 3.13+

## Quick start

```bash
uv sync
uv run flask --app 'app:create_app()' run --debug
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

## Project layout

```text
.
├── AGENTS.md
├── app/
│   ├── __init__.py
│   └── routes.py
├── pyproject.toml
├── tests/
│   ├── conftest.py
│   └── test_app.py
└── README.md
```
