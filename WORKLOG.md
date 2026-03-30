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
