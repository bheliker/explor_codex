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
- Migration verification DBs live under `./.codex-tmp/migration-dbs/`
- Migrate the DB: `sqlite+pysqlite:////Users/bheliker/Documents/_Projects/explor/explor_codex/.codex-tmp/migration-dbs/*.db`
	- `uv run flask --app 'app:create_app()' db upgrade`
	- `DATABASE_URL=sqlite+pysqlite:////Users/bheliker/Documents/_Projects/explor/explor_codex/.codex-tmp/migration-dbs/<task>.db uv run flask --app 'app:create_app()' db upgrade`

## Code Layout
- Application code lives in `app/`
- Tests live in `tests/`
- Templates belong in `templates/`
- Static assets belong in `static/`

## Expectations
- Keep changes minimal and targeted.
- Add or update tests for behavior changes.
- Run tests, lint, and mypy before finishing substantive changes.
- Read `WORKLOG.md` at the start of a new session before planning work.
- Append a concise dated entry to `WORKLOG.md` after each substantive session covering what was investigated, what changed, what was decided, and why.

## Commit Workflow
- After each code change, propose a git commit title and body.
	- `git add ` commands are always ok as part of a commit
- Wait for explicit user approval before running `git add` or `git commit`.
	- If Agents are running independently of the User, create and commit to a branch and only ask permission to merge into main when the feature or task is complete and working on the branch.
- Only create the commit or merge after the user approves the proposed message.

## Project goals
- 

## Architecture notes



## Working notes

- Prefer short, specific instructions over long general advice.
- Prefer repo-local migration verification databases over shared `/tmp`.
- Update this file as the project evolves.
