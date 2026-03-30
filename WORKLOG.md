# WORKLOG.md

This file records session history for `explor_codex` so future work can resume with context.

## How to use this log
- Read this file at the start of a new session before planning or making changes.
- Append a new dated entry after each substantive work session.
- Capture what we investigated, what changed, what we decided, and why.
- Prefer concise, high-signal notes over exhaustive transcripts.

## 2026-03-29

### Investigated
- Audited what remained from `explor_alpha` before redesigning search.
- Confirmed the remaining unported pieces were mostly old framework-era or optional product features:
  - `Role`, `RolesUsers`, `PaginatedAPIMixin`, `group_members`, `group_images`
  - optional joins such as `followers` and `calendar_subscribers`
- Evaluated whether DuckDB should replace SQLite or Postgres for local/test workflows.

### Changed
- Added a portable app-level search architecture:
  - [app/models/search_document.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/models/search_document.py)
  - [app/services/search.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/services/search.py)
  - [migrations/versions/1cc7da553e57_add_search_documents_table.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/migrations/versions/1cc7da553e57_add_search_documents_table.py)
- Wired search indexing into create flows for:
  - groups
  - routes
  - segments
  - events
  - points of interest
  - activities
- Added search API endpoints in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py):
  - `GET /api/search`
  - `POST /api/search/reindex`
- Added test coverage in [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py)
- Updated [README.md](/Users/bheliker/Documents/_Projects/explor/explor_codex/README.md) to document the search surface.
- Added this worklog and updated [AGENTS.md](/Users/bheliker/Documents/_Projects/explor/explor_codex/AGENTS.md) to require reading/updating it in future sessions.

### Decisions
- Stop importing old models for now and move into search/admin/UI redesign on top of the modernized domain.
- Keep search app-level and cross-database first, using a `search_document` table plus normalized text matching.
- Keep Postgres/PostGIS as the authoritative local app database.
- Keep SQLite for disposable migration verification.
- Do not replace the app’s main local/test DB behavior with DuckDB.
- Treat DuckDB as optional future tooling for analytics or search experiments, not as the primary compatibility path.

### Why
- The remaining old models were either obsolete under the new architecture or optional product features rather than prerequisites.
- App-level search gives us portability, easier tests, and simpler migrations while the data model is still evolving.
- Postgres/PostGIS is still the best way to preserve geospatial correctness and compatibility with the inherited schema shape.
- SQLite remains useful as a lightweight migration verifier because it is already integrated into the repo-local disposable DB workflow.

### Notes for the next session
- The next likely feature area is thin admin/UI work on top of the new search API.
- Another good option is improving search freshness for future update/edit flows so reindexing is less manual.
- Search is currently indexed on create flows and via explicit rebuilds; update-path indexing has not been added yet.

## 2026-03-29 (Search Freshness)

### Investigated
- Reviewed the new search architecture to see how freshness was currently maintained.
- Confirmed search documents were only being created during service-layer create flows plus explicit rebuilds.
- Checked whether real update routes already existed; they do not yet, so freshness needed to work for direct ORM edits too.

### Changed
- Added session-level search listeners in [app/services/search.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/services/search.py) using SQLAlchemy session hooks.
- Registered those listeners from [app/extensions.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/extensions.py).
- Removed the manual per-service `index_instance(...)` calls from create services so search indexing now happens in one shared place.
- Added tests in [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) proving that:
  - direct model edits refresh search results
  - model deletes remove search documents

### Decisions
- Keep explicit `POST /api/search/reindex` as a deterministic recovery/rebuild path.
- Move freshness behavior into ORM session hooks instead of scattering indexing logic through every service or future route.

### Why
- This covers direct ORM edits now and future update/edit flows later without needing to remember search bookkeeping at every call site.
- One central indexing path is easier to reason about and less error-prone than repeated per-service indexing calls.

### Notes for the next session
- Search freshness now covers create, update, and delete events that go through the ORM session.
- The next likely step is building thin admin/UI surfaces on top of the search API and current model/service layer.

## 2026-03-29 (Thin Admin UI)

### Investigated
- Checked whether the project already had any templates or static assets; it did not.
- Confirmed the search API was the best first UI anchor because it already spans the rebuilt domain.
- Found that the Flask app factory was not yet wired to the repo-root `templates/` directory.

### Changed
- Added a thin server-rendered admin search console:
  - [templates/base.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/base.html)
  - [templates/admin/search.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/search.html)
- Added `GET /admin/search` in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py).
- Updated [app/__init__.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/__init__.py) so the Flask app correctly uses repo-root `templates/` and `static/`.
- Added HTML route coverage in [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py).
- Updated [README.md](/Users/bheliker/Documents/_Projects/explor/explor_codex/README.md) to document the new admin search surface.

### Decisions
- Start UI work with a thin server-rendered tool rather than introducing a heavier admin framework.
- Keep the UI directly backed by the existing search service layer instead of duplicating query logic in templates or routes.

### Why
- This gives the project a practical browser entry point quickly while preserving the API-first architecture underneath.
- It also creates a lightweight place to inspect search behavior while future admin pages are still being designed.

### Notes for the next session
- There is now a usable HTML admin foothold at `/admin/search`.
- The next likely UI step is either a domain dashboard or detail pages for core entities reached from search results.

## 2026-03-29 (Read-Only Detail Pages)

### Investigated
- Built on the new admin search console to decide the next most useful read-only HTML slice.
- Confirmed the search results needed navigable detail pages to become a real inspection flow.
- Found and fixed an app-factory gap earlier in the same UI effort: repo-root templates needed to be explicitly wired into Flask.

### Changed
- Added thin read-only detail pages for:
  - groups
  - routes
  - segments
  - events
  - points of interest
  - activities
- Added [templates/admin/detail.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/detail.html).
- Updated [templates/admin/search.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/search.html) so search results link to the new detail pages.
- Added the corresponding admin routes and lightweight detail helpers in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py).
- Extended [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) for result-link rendering and representative detail pages.
- Updated [README.md](/Users/bheliker/Documents/_Projects/explor/explor_codex/README.md) to document the new HTML endpoints.

### Decisions
- Keep these pages read-only for now and continue using the existing route/model/service layer as the source of truth.
- Use one generic detail template plus route-side formatting helpers instead of building separate heavy templates for each entity.

### Why
- This keeps the UI surface intentionally thin while still making the admin search page genuinely useful for inspection.
- It also gives future editing/admin work a stable destination structure to build on.

### Notes for the next session
- The HTML admin surface now supports both search and drill-down inspection.
- The next likely step is either:
  - entity edit forms for a few high-value records, or
  - an admin dashboard that summarizes counts, recent records, and system health.

## 2026-03-30 (Admin Edit Flows)

### Investigated
- Built on the search and read-only detail pages to add the first practical write path in the browser.
- Reused the current service layer and search freshness hooks rather than introducing separate form-only update logic.
- Split the work into two checkpoints:
  - `Group` first
  - then `Route` and `Event` on the same reusable edit pattern

### Changed
- Added a reusable edit template at [templates/admin/edit.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/edit.html).
- Added admin edit flows for:
  - groups
  - routes
  - events
- Added update services in:
  - [app/services/groups.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/services/groups.py)
  - [app/services/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/services/routes.py)
  - [app/services/events.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/services/events.py)
- Added edit routes plus form parsing helpers in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py).
- Linked relevant detail pages to their edit routes.
- Extended [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) to cover:
  - group edit flow
  - route edit flow
  - event edit flow
  - search freshness after admin edits
- Updated [README.md](/Users/bheliker/Documents/_Projects/explor/explor_codex/README.md) with the new edit endpoints.

### Decisions
- Keep the edit UI intentionally thin and form-post based for now.
- Use the existing ORM/session-driven search freshness hooks so edits automatically update search results.
- Limit this first editing slice to `Group`, `Route`, and `Event`, which are the highest-value core entities.

### Why
- This completes the first full browser admin loop for important records:
  - search
  - inspect
  - edit
- It also proves that the service layer and search freshness work cleanly under real edit flows.

### Notes for the next session
- The admin UI now supports read-only detail pages and edit forms for groups, routes, and events.
- The next likely step is either:
  - creation forms in the admin UI, or
  - an admin dashboard with recent records and quick links.
