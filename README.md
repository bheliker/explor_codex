# explor_codex

Plain, non-packaged Flask app template managed with `uv`.

## Requirements

- `uv`
- Python 3.13+

## Quick start

```bash
uv sync
uv run flask --app app run --debug
```

The app exposes:

- `/`
- `/health`

## Development checks

```bash
uv run ruff check .
uv run pytest
```

## Project layout

```text
.
├── AGENTS.md
├── app.py
├── pyproject.toml
├── tests/
│   └── test_app.py
└── README.md
```
