# AGENTS.md

This file is the local instruction scratchpad for future Codex work in this repository.

## Environment
- Use `uv` for dependency management and command execution.
- Install dependencies with `uv sync`.

## Commands
- Run the app: `uv run flask --app 'app:create_app()' run --debug`
- Run tests: `uv run pytest`
- Run lint: `uv run ruff check .`
- Check formatting: `uv run ruff format --check .`
- Format code: `uv run ruff format .`
- Run type checks: `uv run mypy app tests`
- Migrate the DB: `sqlite+pysqlite:////tmp/*.db`
	- `uv run flask --app 'app:create_app()' db upgrade`
	- `DATABASE_URL=sqlite+pysqlite:////tmp/explor_calendar_verify.db uv run flask --app 'app:create_app()' db upgrade`

## Code Layout
- Application code lives in `app/`
- Tests live in `tests/`
- Templates belong in `templates/`
- Static assets belong in `static/`

## Expectations
- Keep changes minimal and targeted.
- Add or update tests for behavior changes.
- Run tests, lint, and mypy before finishing substantive changes.

## Commit Workflow
- After each code change, propose a git commit title and body.
- Wait for explicit user approval before running `git add` or `git commit`.
	- If Agents are running independently of the User, create and commit to a branch and only ask permission to merge into main when the feature or task is complete and working on the branch.
- Only create the commit or merge after the user approves the proposed message.

## Project goals
- 

## Architecture notes



## Working notes

- Prefer short, specific instructions over long general advice.
- Update this file as the project evolves.
