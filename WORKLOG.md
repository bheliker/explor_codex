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

## 2026-03-30 (Admin Dashboard And Create Forms)

### Investigated
- Built on the new read-only and edit flows to add a stronger browser landing point.
- Reused the same thin admin template/style system instead of introducing a separate dashboard stack.
- Kept the creation scope focused on the same highest-value entities already supported for editing:
  - groups
  - routes
  - events

### Changed
- Added an admin dashboard at `/admin` via [templates/admin/dashboard.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/dashboard.html) and [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py).
- Added browser-based creation forms for:
  - `/admin/groups/new`
  - `/admin/routes/new`
  - `/admin/events/new`
- Extended [templates/admin/edit.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/edit.html) so it supports both create and edit modes.
- Added dashboard helper functions in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) for counts and recent records.
- Extended [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) for:
  - dashboard rendering
  - group creation through the admin UI
  - route creation through the admin UI
  - event creation through the admin UI
  - search freshness after those creates
- Updated [README.md](/Users/bheliker/Documents/_Projects/explor/explor_codex/README.md) with the new admin endpoints.

### Decisions

## 2026-04-07 (Route And Segment Browser Refinements)

### Investigated
- Reviewed the first public route and segment browser pass against real browser behavior and payload size.
- Confirmed the browse surfaces needed tighter result caps, lighter map payloads, and more predictable Leaflet lifecycle handling before moving into broader polish.
- Followed the next round of UX requests around paging, full-height mapping, area jumping, and full-database text search.

### Changed
- Reduced the public route and segment browse payload shape to summary geometry only and kept the browser limit capped server-side.
- Added real Leaflet map rendering with server-backed viewport querying, richer club/event/terrain filters, and offset pagination for `/routes` and `/segments`.
- Hardened the map client in [static/js/collection_browser.js](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/js/collection_browser.js) to avoid duplicate Leaflet initialization and suppress fetch loops from internal map moves.
- Increased the public browser cap from 20 to 30 records per request in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py).
- Added `/api/browser/areas` plus area-search UI so users can jump the map to another city or state from [templates/public/entity_browser.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/entity_browser.html).
- Updated the main browse search so typed queries automatically run against the full dataset while map-area browsing remains available as an explicit mode.
- Made the map panel fill the viewport more completely in [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css).
- Hid zero-value club and event count pills and stopped rendering blank rating/grade stats.
- Extended regression coverage in [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) for the 30-result cap, area search, zero-count hiding, and browser API pagination/filtering.

### Decisions
- Keep public browser responses intentionally small and paged, even when the map surface becomes richer.
- Treat free-text query as a full-database search affordance and keep map-area filtering as a separate, reversible mode.
- Skip empty or zero-value secondary UI badges rather than rendering placeholders that make sparse records feel broken.

### Why
- The public browse pages are the main navigation layer for the site, so responsiveness and clarity matter more than loading every possible record at once.
- Area jumping and full-database text search make it much faster to reorient the browse experience without forcing the user to pan manually across the map.
- Removing empty stats and zero badges keeps cards focused on signal instead of visual noise.

### Notes for the next session
- The next likely browse refinements are marker clustering, deeper side-panel previews, and map-driven highlighting for hovered list items.
- If full-database search needs to go beyond field matching, the existing `search_document` index is a strong candidate for powering the browse text query.

## 2026-04-08 (Browse Panel Cleanup)

### Investigated
- Reviewed the public browse control panel after the larger route and segment browser feature work landed.
- Identified that the left-side browse controls had too many always-visible actions competing at once, especially around search mode, filters, and area jumping.

### Changed

## 2026-04-08 (HTML And CSS Readability Pass)

### Investigated
- Reviewed the shared template and stylesheet entry points to find the highest-leverage places for future human editing.
- Focused on files that multiple surfaces inherit from or reuse directly:
  - [templates/base.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/base.html)
  - [templates/admin/detail.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/detail.html)
  - [templates/public/entity_browser.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/entity_browser.html)
  - [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css)

### Changed
- Added structural comments to shared templates so major page regions now have clear begin/end markers.
- Added concise notes explaining where route-provided variables feed the templates and where future edits should happen first.
- Added section comments to the shared stylesheet so design-token, navigation, hero, and panel/layout areas are easier to locate and modify.
- Cleaned up a few stale inline comment remnants in the detail template while keeping behavior intact.

### Decisions
- Prefer section-level comments over line-by-line commentary so files stay readable instead of becoming noisier.
- Document shared seams first rather than every leaf template, because most future edits should start from the shared shell, shared detail view, browser template, and shared CSS.

### Why
- The project is now visually richer and more componentized, which makes source readability more important for future manual editing.
- Clear “change it here” notes reduce the amount of reverse engineering needed when adjusting copy, layout, design tokens, or route-fed variables.

### Notes for the next session
- If we continue this pass, the next best files to annotate are the auth templates and any page-specific JavaScript controllers.
- Shared template comments should stay brief and structural; avoid turning templates into prose documents.
- Simplified the main browse controls in [templates/public/entity_browser.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/entity_browser.html) into a primary search row with a smaller Nearby / Full database mode toggle.
- Moved lower-frequency controls behind a `More filters` reveal so sort, club, terrain, area jump, and map reset stay available without dominating the panel.
- Added a `Clear` action and conditional area-match rendering in [static/js/collection_browser.js](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/js/collection_browser.js).
- Tightened the browse-panel presentation in [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css).
- Updated page assertions in [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) to match the refined control surface.

### Decisions
- Keep the most common browse actions visible at all times:
  - search
  - browse mode
  - favorites
  - event-linked toggle
- Treat more specific narrowing and map-jump controls as progressive disclosure.

### Why
- These pages are the main navigation surface, so reducing panel clutter improves scannability and makes the map/list behavior easier to understand.

### Notes for the next session
- The next UI pass could further simplify result cards or add hover-linked highlighting between list items and map markers.

## 2026-04-08 (Selective Geometry Fix Transplant)

### Investigated
- Audited the older `fix/geometry-and-code-cleanup` branch to see whether its work had already landed on the current browser branch.
- Confirmed the branch mixed useful geometry fixes with unrelated CSRF, template, and auth churn, so it was not a good candidate for a direct merge.
- Compared the geometry-specific commits against the current code and identified the missing pieces:
  - multiline/feature-collection storage conversion
  - multiline detail map rendering
  - shared route helper support for multi-part linework

### Changed
- Updated [app/geometry.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/geometry.py) so stored line geometry accepts `LineString`, `MultiLineString`, and `FeatureCollection` linework, and widened the ORM geometry type wrappers to `GEOMETRY` / `GEOMETRYZ`.
- Updated [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) so shared geometry helpers preserve separate line parts for Leaflet rendering and SVG path generation.
- Extended the public browser geometry handling in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) and [static/js/collection_browser.js](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/js/collection_browser.js) so multiline route or segment summaries still render on the browse map.
- Updated [static/js/detail_visuals.js](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/js/detail_visuals.js) so detail-map visuals render multiline paths correctly without collapsing them into one flat sequence.
- Added regression tests in [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) for feature-collection storage conversion, multiline Leaflet lat/lng conversion, and browser geometry passthrough.

### Decisions
- Do not merge `fix/geometry-and-code-cleanup` directly.
- Instead, manually transplant the geometry-only fixes into the active branch and leave the unrelated CSRF/template sweep for a separate decision.

### Why
- This keeps the current branch aligned with the newer route/segment browser work while still capturing the substantive geometry correctness fixes from the older side branch.

### Notes for the next session
- If we want the rest of `fix/geometry-and-code-cleanup`, it should be split into smaller, reviewable slices rather than merged whole.

## 2026-04-08 (Selective CSRF And Auth Hardening)

### Investigated
- Reviewed the older mixed branch again, this time isolating the CSRF/auth-related work from the geometry and formatting churn.
- Confirmed the highest-value pieces were:
  - app-wide CSRF protection
  - hidden CSRF tokens in real HTML forms
  - test config compatibility
  - explicit API exemptions for JSON endpoints
  - broader `AdminFormError` handling in admin user forms

### Changed
- Added `flask-wtf` to [pyproject.toml](/Users/bheliker/Documents/_Projects/explor/explor_codex/pyproject.toml) and initialized `CSRFProtect` in [app/extensions.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/extensions.py).
- Disabled CSRF in [app/config.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/config.py) only for `TestConfig`.
- Added an app-level CSRF error handler and exempted JSON API POST routes in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py).
- Broadened admin user create/edit error handling in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) so `AdminFormError` flashes cleanly there too.
- Added hidden CSRF tokens to the real HTML POST forms in:
  - [templates/base.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/base.html)
  - [templates/admin/edit.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/edit.html)
  - [templates/auth/login.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/login.html)
  - [templates/auth/signup.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/signup.html)
  - [templates/auth/account_edit.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/account_edit.html)
  - [templates/auth/password_reset.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/password_reset.html)
  - [templates/auth/password_reset_request.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/password_reset_request.html)
- Added tests in [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) covering form token rendering, test-config CSRF disablement, and exempt JSON API behavior under enabled CSRF.

### Decisions
- Keep the auth/template portion narrowly focused on functional hardening and avoid bringing over the old branch’s broad formatting-only template churn.
- Continue treating JSON APIs separately from HTML forms by exempting the machine-oriented POST endpoints.

### Why
- This brings the meaningful security and reliability improvements forward without risking unnecessary UI regressions from unrelated template rewrites.

### Notes for the next session
- If we later want stricter API auth/CSRF policy, that should be handled as an explicit API security pass rather than bundled into unrelated UI work.

## 2026-04-02 (Event Maps, Stats Bar, And Units Migration Repair)

### Investigated
- Extended the old Explor map-first detail treatment to events and calendars, then verified how route, segment, activity, and event stats should be presented in the new detail pages.
- Diagnosed a live Postgres failure after adding `User.units`; the application database was stamped at Alembic revision `56c4b0d8a9c2`, but that migration file was missing from the current branch.
- Confirmed the new product requirement that metric remains the backend truth for real-world measurements and imperial is display-only.

### Changed
- Added map-first detail support and shared stats-bar rendering for routes, segments, activities, events, and calendars in:
  - [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py)
  - [templates/admin/detail.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/detail.html)
  - [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css)
  - [static/js/detail_visuals.js](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/js/detail_visuals.js)
- Added `User.units` support through model, auth/account flows, and migration:
  - [app/models/user.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/models/user.py)
  - [templates/auth/account.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/account.html)
  - [templates/auth/account_edit.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/account_edit.html)
  - [migrations/versions/f24d3d3b9c1a_add_user_units_preference.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/migrations/versions/f24d3d3b9c1a_add_user_units_preference.py)
- Restored the missing geometry migration revision so the live database could upgrade cleanly again:
  - [migrations/versions/56c4b0d8a9c2_widen_line_geometry_columns.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/migrations/versions/56c4b0d8a9c2_widen_line_geometry_columns.py)
- Updated measurement formatting and tests so distances are treated as meters in storage and converted only at render time.

### Decisions
- Keep metric as the only backend source-of-truth unit system for real-world measurements.
- Preserve user unit preference purely as a presentation concern.
- Keep the restored `56c4b0d8a9c2` revision in the branch history because the live database already depends on it.

### Why
- The live application database could not load users or admin pages until the missing revision chain and quoted `user` table migration SQL were repaired.
- Treating metric as the storage truth avoids unit ambiguity across imported source data while still supporting imperial display for riders who want it.
- Reusing one map/stats detail system across map-first entities keeps the new design language closer to the original Explor product rhythm without reviving the old frontend stack.

### Notes for the next session
- The real Postgres database and repo-local disposable SQLite migration DB both upgrade cleanly through `f24d3d3b9c1a`.
- Route detail tests now assert rendered metric display rather than older literal source formatting.
- This branch still has uncommitted changes after the earlier checkpoint commit and should be committed before the next major phase.
- Use `/admin` as the browser entry point for the admin surface.
- Keep create forms limited to groups, routes, and events for now to match the current edit coverage.
- Continue relying on the existing service layer and ORM search freshness hooks so new records immediately show up in search/admin views.

### Why
- This rounds out the first practical browser admin workflow:
  - dashboard
  - create
  - search
  - inspect
  - edit
- It also gives future work a stable place for quick links, summary stats, and additional admin tools.

### Notes for the next session
- The admin HTML surface now supports dashboard, create, search, inspect, and edit for the core entities.
- The next likely step is either:
  - expanding create/edit coverage to more entity types, or
  - adding navigation polish and small quality-of-life improvements like success messaging and recent activity links.

## 2026-03-30 (Admin Polish And Coverage Expansion)

### Investigated
- Focused on the remaining admin quality gaps after the first dashboard/create/edit pass:
  - success and error feedback
  - stronger navigation between pages
  - recent-activity links on detail pages
  - create/edit coverage for the remaining core entity types
- Confirmed the remaining high-value admin-visible entities were:
  - segments
  - points of interest
  - activities

### Changed
- Added flash messaging and stronger top-level navigation in [templates/base.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/base.html).
- Added recent-activity links to [templates/admin/detail.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/detail.html) backed by recent search documents from [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py).
- Replaced hard admin form aborts with friendlier validation messages for browser form flows in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py).
- Expanded dashboard sections and quick-create links in [templates/admin/dashboard.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/dashboard.html).
- Added create and edit coverage for:
  - segments
  - points of interest
  - activities
- Added the supporting update services in:
  - [app/services/segments.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/services/segments.py)
  - [app/services/points_of_interest.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/services/points_of_interest.py)
  - [app/services/activities.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/services/activities.py)
- Extended [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) with admin polish coverage plus create/edit flows for the new entity types.
- Updated [README.md](/Users/bheliker/Documents/_Projects/explor/explor_codex/README.md) to reflect the broader admin surface.

### Decisions
- Keep using the shared admin form template and route-side formatting/validation helpers rather than introducing separate per-entity form systems.
- Use recent search documents as the source for “recent activity” links so the navigation stays tied to the same cross-entity search layer.
- Treat segments, points of interest, and activities as the remaining core admin entities for this phase; images and other support tables remain secondary.

### Why
- This turns the admin UI from a promising scaffold into a coherent daily-use surface:
  - clearer navigation
  - feedback after actions
  - friendlier validation
  - fuller entity coverage
- It also closes the loop on the user-reported confusion around event creation with invalid related IDs by surfacing those issues as admin messages instead of opaque 404s.

### Notes for the next session
- The admin HTML surface now supports create/edit coverage for groups, routes, segments, events, points of interest, and activities.
- The next likely step is either:
  - secondary admin entities like images, links, dues, and fees, or
  - deeper UX polish such as breadcrumbs, richer success states, and inline related-record pickers.

## 2026-03-30 (Auth Stack Completion)

### Investigated
- Revisited the earlier auth groundwork and confirmed it only covered the foundation:
  - `User`
  - password hashing
  - reset-token primitives
  - `Flask-Login` initialization
- Identified the remaining missing product-level auth pieces:
  - login/logout
  - signup
  - password reset forms
  - site-wide admin authorization
  - admin user-management pages
- Also found a real policy gap: the HTML admin surface had no auth gate, and the write-side JSON API was still publicly writable.

### Changed
- Added a real `site_admin` flag to [app/models/user.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/models/user.py) and the migration [migrations/versions/9815df31c0ad_add_site_admin_flag_to_users.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/migrations/versions/9815df31c0ad_add_site_admin_flag_to_users.py).
- Added user-domain services in [app/services/users.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/services/users.py) for:
  - user creation
  - user updates
  - authentication
  - login timestamp recording
  - user listing
- Rebuilt [app/auth.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/auth.py) into a real auth blueprint with:
  - `/auth/login`
  - `/auth/logout`
  - `/auth/signup`
  - `/auth/password-reset`
  - `/auth/password-reset/<token>`
  - `/auth/account`
- Registered the auth blueprint and a simple HTML `403` page from [app/__init__.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/__init__.py).
- Added auth and error templates:
  - [templates/auth/login.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/login.html)
  - [templates/auth/signup.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/signup.html)
  - [templates/auth/password_reset_request.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/password_reset_request.html)
  - [templates/auth/password_reset.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/password_reset.html)
  - [templates/auth/account.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/account.html)
  - [templates/errors/403.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/errors/403.html)
- Added real admin user-management pages in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) and [templates/admin/users.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/users.html):
  - `/admin/users`
  - `/admin/users/new`
  - `/admin/users/<id>`
  - `/admin/users/<id>/edit`
- Extended the shared base/dashboard/admin navigation so users and auth flows are part of the main browser surface.
- Added authorization enforcement in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py):
  - all `/admin/*` HTML routes require an authenticated active site admin
  - write-side `/api/*` routes require an authenticated active site admin
  - read-only GET API routes remain open
- Extended [tests/conftest.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/conftest.py) and [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) with:
  - signup/login/logout coverage
  - password reset request/reset coverage
  - admin and API authorization coverage
  - admin user-management coverage
  - updated admin/API tests using authenticated site-admin clients

### Decisions
- Use a simple `site_admin` boolean on `User` instead of reviving the old `Role` / `RolesUsers` stack from `explor_alpha`.
- Auto-promote the first registered user to site admin so a fresh local instance is bootstrappable without manual SQL.
- Ensure at least one active site admin always remains by blocking edits that would remove the last one.
- Keep signup optional via config (`AUTH_SIGNUP_ENABLED`) rather than hard-coding public registration forever.
- Keep password reset local/dev friendly by exposing the generated reset link in the browser when `AUTH_SHOW_RESET_LINKS` is enabled, instead of pretending email delivery already exists.

### Why
- This finishes the auth stack in a way that fits the rebuilt app instead of reintroducing the older Flask-Security-era complexity.
- A dedicated site-admin flag is enough for current project needs, while group membership roles continue to handle group-local permissions separately.
- Protecting both the browser admin and the write-side JSON API closes the biggest remaining security gap in the new app.

### Notes for the next session
- The project now has real end-user auth flows and real site-admin authorization.
- The next likely step is either:
  - secondary admin entities like images, links, dues, and fees, now that user/admin management is in place, or
  - deeper auth polish such as email delivery for reset links, remember-me behavior, or per-feature authorization beyond the site-admin gate.

## 2026-03-30 (Secondary Admin Entities And Account Polish)

### Investigated
- Looked at the remaining models that already existed in the rebuilt schema but still lacked browser admin coverage:
  - images
  - shared external links
  - group dues
  - event fees
- Reviewed the new auth/account surface and identified the main missing self-service piece: users could view their account but not edit it without using the admin user-management pages.

### Changed
- Added update services for secondary admin entities in:
  - [app/services/images.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/services/images.py)
  - [app/services/groups.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/services/groups.py)
  - [app/services/events.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/services/events.py)
- Expanded [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) with browser admin list/detail/create/edit flows for:
  - `/admin/images`
  - `/admin/links`
  - `/admin/dues`
  - `/admin/fees`
- Added the shared list template [templates/admin/collection.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/collection.html) for those record collections.
- Expanded [templates/admin/dashboard.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/dashboard.html) with quick-create links for the new secondary entities.
- Added account self-editing via:
  - `/auth/account/edit`
  - [templates/auth/account_edit.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/account_edit.html)
- Updated [templates/auth/account.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/account.html) so the account page links into the new edit flow.
- Extended [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) with:
  - account edit coverage
  - image admin create/edit coverage
  - link admin create/edit coverage
  - dues admin create/edit coverage
  - fee admin create/edit coverage
  - dashboard quick-link coverage for the new admin pages

### Decisions
- Keep secondary entity admin flows on the same shared thin-template pattern as the primary entities instead of adding a separate mini-framework.
- Treat shared external links as one admin record type even though they can belong to either a group or a route.
- Let users self-edit profile/contact/location metadata from the account area, while still reserving activation and site-admin controls for the admin user-management pages.

### Why
- These records were already part of the rebuilt domain, so giving them consistent browser admin coverage increases the usefulness of the current app more than importing additional schema would.
- Account self-editing rounds out the auth work so normal users are not forced through site-admin-only pages for simple profile updates.

### Notes for the next session
- The admin browser surface now covers both the primary domain entities and the most important secondary support records.
- The next likely step is either:
  - richer UI polish such as breadcrumbs, better related-record selectors, and image previews, or
  - deeper auth delivery work such as real password-reset email sending and remember-me/session polish.

## 2026-03-30 (UX Polish And Reset Delivery)

### Investigated
- Followed up on the most obvious admin/auth UX rough edges left after the secondary-entity pass:
  - raw related-record ID entry with no guidance
  - image-heavy pages with no actual previews
  - password reset still behaving more like a local token generator than an email-delivery flow

### Changed
- Added a lightweight email delivery service in [app/services/email.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/services/email.py).
- Added in-memory outbox support from [app/extensions.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/extensions.py) and new config knobs in [app/config.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/config.py):
  - `EMAIL_DELIVERY_MODE`
  - `EMAIL_FROM`
- Updated [app/auth.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/auth.py) so password reset requests now create and queue a reset email, while still showing a browser preview in local/dev mode.
- Updated [templates/auth/password_reset_request.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/password_reset_request.html) to show an email preview block instead of only a bare link.
- Added shared admin field support for datalist-style related-record suggestions in [templates/admin/edit.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/edit.html) and [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py).
- Applied those related-record suggestions to the most common linked-ID fields, including:
  - event route/activity references
  - activity route references
  - image ownership references
  - link owners
  - dues group references
  - fee event references
- Added media preview support in [templates/admin/detail.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/detail.html) and wired it from [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) for image-heavy records such as:
  - images
  - groups with hero photos
  - routes with map thumbnails
  - events with photo/logo/profile media
  - activities with photo URLs
- Extended [templates/base.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/base.html) with the shared preview/help styling.
- Extended [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) to cover:
  - password reset email outbox behavior
  - email preview rendering
  - image detail previews
  - related-record suggestion rendering on admin forms

### Decisions
- Keep reset delivery local-first for now by queuing mail in memory instead of introducing a real provider before the app needs one.
- Use datalist suggestions to improve raw-ID fields immediately without forcing a heavier autocomplete stack into the thin server-rendered admin UI.
- Add previews only where we already have stable media URLs in the current schema instead of creating placeholder preview systems for every entity.

### Why
- These changes make the current browser/admin/auth flows noticeably friendlier without changing the underlying architecture or data contracts.
- The outbox approach keeps tests deterministic and gives us a clean seam for plugging in real email later.

### Notes for the next session
- The app now has a credible local reset-email story plus better admin affordances for linked records and media-heavy pages.
- The next likely step is either:
  - deeper UI polish such as breadcrumbs, tabbed detail views, and richer related-record selection, or
  - a real outbound email provider implementation to replace the in-memory outbox in non-dev environments.

## 2026-03-30 (Design Port Audit)

### Investigated
- Compared the current `explor_codex` UI surface against the locally cloned `../explor_alpha` repo.
- Reviewed the current app factory, admin routes, and shared templates to find safe design port seams.
- Audited the old repo's base templates, landing page, dashboard, detail pages, and asset pipeline shape.

### Changed
- No product code changes.
- Created branch `codex/design-port-audit` to isolate follow-on design merge work from `main`.

### Decisions
- Start the design merge at the shared shell layer, not by copying old page templates directly.
- Preserve the current route and service contracts in `app/routes.py` and the service layer, and port visuals into new repo-local templates/static assets around them.
- Prioritize one vertical slice first:
  - admin dashboard/search/detail pages, or
  - public landing page if marketing value matters more than admin usability.

### Why
- The current app already has stable server-rendered entry points and CRUD/search flows that match the new backend.
- The old repo's UI is tightly coupled to a larger Bootstrap/jQuery asset stack, modal system, and page-specific data assumptions, so direct template reuse would create regressions and dependency drag.

### Notes for the next session
- Best migration seam:
  - move old design tokens, fonts, imagery, and shell patterns into a new real `static/` tree plus a modernized shared base template
  - then re-skin the existing admin templates incrementally
- Likely parallel workstreams:
  - asset inventory and licensing cleanup
  - template/content mapping from old pages to current entities
  - static/CSS extraction and reduction from the old asset bundle

## 2026-03-30 (First Design Slice)

### Investigated
- Compared the current admin templates against the strongest reusable visual patterns in `../explor_alpha`.
- Confirmed the safest first slice was the shared shell plus the browser-backed admin dashboard, search, and detail pages.
- Audited likely risks from the old stack and avoided directly importing its Bootstrap, jQuery, map, and modal dependencies.

### Changed
- Replaced the inline shared styling in [templates/base.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/base.html) with a repo-local stylesheet at [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css).
- Reworked [templates/base.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/base.html) into a stronger shared shell with:
  - branded top navigation
  - glassy surface treatment
  - support for the new design-system classes
- Re-skinned:
  - [templates/admin/dashboard.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/dashboard.html)
  - [templates/admin/search.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/search.html)
  - [templates/admin/detail.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/detail.html)
  - [templates/admin/edit.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/edit.html)
- Ported old-repo design cues into the new admin slice:
  - darker cinematic hero sections
  - stronger uppercase labels
  - stat cards
  - split-column rails
  - action rows
  - denser card treatments
- Kept all existing route, model, and service contracts intact so the new backend remained unchanged.

### Decisions
- Translate the old design language into a lightweight repo-local CSS layer rather than importing the legacy asset pipeline.
- Avoid directly porting old commercial/custom font assets until licensing is confirmed.
- Extend the visual refresh to the shared edit template too, so the first slice feels coherent across inspect and write flows.

### Why
- This gives the project a real proof that old `explor_alpha` design ideas can be merged into the rebuilt Flask app without dragging old frontend dependencies or backend assumptions back in.
- Moving the styling into `static/css/admin.css` also gives future UI work a stable place to keep extending the design system.

### Verification
- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy app tests`

### Notes for the next session
- The first design slice now covers the shared shell plus dashboard, search, detail, and edit flows.
- The next likely step is either:
  - extending the same language to collection and auth pages, or
  - introducing a public-facing landing page slice that borrows from the old marketing/hero patterns while staying backend-light.

## 2026-03-31 (Public/Auth And Collection Design Rollout)

### Investigated
- Reviewed the remaining server-rendered pages that still sat outside the first design slice:
  - collection pages
  - user directory
  - auth flows
  - account pages
- Compared those surfaces to the old `explor_alpha` landing/auth composition to find the minimum viable public slice that would not require reintroducing video, modal, or JS-heavy behavior.
- Confirmed it was safer to preserve the JSON contract at `/` and add a separate HTML landing route instead of silently changing the existing readiness endpoint.

### Changed
- Added a backend-light public landing page at [templates/public/landing.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/landing.html) with its route in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py).
- Updated [templates/base.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/base.html) so anonymous navigation points toward the new public landing surface.
- Extended the shared stylesheet in [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css) with landing-page layout and supporting card/section styles.
- Re-skinned:
  - [templates/admin/collection.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/collection.html)
  - [templates/admin/users.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/users.html)
  - [templates/auth/login.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/login.html)
  - [templates/auth/signup.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/signup.html)
  - [templates/auth/account.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/account.html)
  - [templates/auth/account_edit.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/account_edit.html)
  - [templates/auth/password_reset_request.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/password_reset_request.html)
  - [templates/auth/password_reset.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/password_reset.html)
- Added smoke coverage in [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) for:
  - the new public landing route
  - collection admin routes

### Decisions
- Keep `/` as a JSON readiness endpoint for now.
- Use `/landing` as the first public-facing HTML slice until there is a clearer reason to switch to content negotiation or a full homepage replacement.
- Continue translating the old repo’s tone and structure, but not its legacy asset/dependency stack.

### Why
- This broadens the visual merge from “admin-only” into a more cohesive product surface without destabilizing the app’s API behavior.
- It also creates a safe public entry point for future marketing/product storytelling while the backend and domain continue to evolve.

### Verification
- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy app tests`

### Notes for the next session
- The shared design language now spans:
  - public landing
  - auth
  - account
  - collection pages
  - the original admin slice
- The next likely step is either:
  - richer public information architecture, such as browse/search landing experiences, or
  - higher-fidelity visual polish with more original assets and imagery once ownership/licensing is confirmed.

## 2026-03-31 (Design System Primitive Pass)

### Investigated
- Reviewed the refreshed templates after the first two design batches and identified the remaining inconsistency:
  pages shared colors and general style, but not enough reusable structural primitives.
- Revisited the old repo’s strongest transferable qualities:
  - strong editorial hierarchy
  - rails and card groupings
  - cinematic hero treatment
  - concise product-value copy
- Confirmed this phase did not yet require client-side interaction, so adding Alpine would have been premature.

### Changed
- Expanded [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css) with more explicit design-system primitives, including:
  - `content-rail`
  - `collection-grid`
  - `collection-card`
  - `collection-card-hero`
  - `stat-card`
  - `metric-strip`
  - `hero-actions`
  - `section-copy`
- Applied those primitives across:
  - [templates/public/landing.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/landing.html)
  - [templates/admin/dashboard.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/dashboard.html)
  - [templates/admin/search.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/search.html)
  - [templates/admin/detail.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/detail.html)
  - [templates/admin/collection.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/collection.html)
  - [templates/admin/users.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/users.html)
  - [templates/auth/login.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/login.html)
  - [templates/auth/signup.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/signup.html)
  - [templates/auth/account.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/account.html)
  - [templates/auth/account_edit.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/account_edit.html)
  - [templates/auth/password_reset_request.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/password_reset_request.html)
  - [templates/auth/password_reset.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/password_reset.html)

### Decisions
- Keep this layer CSS-first and repo-local.
- Use Alpine only when a page actually needs lightweight interactivity, not as a default dependency with no usage.
- Treat the design system as a set of reusable page-building primitives rather than a page-by-page set of one-off styles.

### Why
- This makes future design ports cheaper and more coherent.
- It also keeps the rebuilt app visually distinctive without pulling in the old frontend stack or introducing unnecessary client complexity.

### Verification
- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy app tests`

### Notes for the next session
- The design system now has clearer reusable primitives for shells, heroes, rails, stat cards, action rows, and collection cards.
- The next likely step is either:
  - adding Alpine-powered lightweight interactions where they materially improve UX, such as live filters or expandable detail sections, or
  - pushing the browse/search and richer entity pages further with stronger imagery, hierarchy, and secondary navigation.

## 2026-03-31 (Public Discover And Richer Entity Presentation)

### Investigated
- Looked for the next page-pattern slice after landing and auth that could reuse the new design primitives without requiring a frontend rewrite.
- Confirmed the existing search index was the best backend-light foundation for a public browse/search experience.
- Identified that entity detail pages could feel richer with better information hierarchy even before introducing any new backend concepts.

### Changed
- Added a public discover route in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) at `/discover`, backed by the existing search document layer.
- Added [templates/public/discover.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/discover.html) as the first public browse/search page using the new repo-local design system.
- Updated [templates/base.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/base.html) so top-level navigation now points to:
  - `Discover`
  - `About`
- Updated [templates/public/landing.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/landing.html) so its primary browse CTA points into the new discover flow.
- Expanded [templates/admin/detail.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/detail.html) so detail pages now surface the first few fields as a highlight strip before the full record details.
- Added coverage in [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) for the new public discover page.

### Decisions
- Keep public discover read-only for now.
- Let public users browse the indexed domain and use clear login CTAs for deeper inspection, rather than prematurely creating a separate public entity-detail stack.
- Continue using generic detail-page enrichment first before building more specialized per-entity presentation layers.

### Why
- This advances the design language into a real browse/search journey instead of stopping at marketing and auth.
- It also improves the usefulness of the existing entity pages by giving key fields more visual emphasis without changing the backend model layer.

### Verification
- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy app tests`

### Notes for the next session
- The current page-pattern rollout now covers:
  - public landing
  - auth/account
  - public discover
  - admin search
  - richer entity detail presentation
- The next likely step is either:
  - Alpine-powered interaction polish for discover/search/detail flows, or
  - deeper per-entity visual storytelling such as related-record sections, better imagery, and secondary navigation.

## 2026-03-31 (Voice, Color, And Alpine Polish)

### Investigated
- Revisited the visual tone after the public discover slice and identified two remaining gaps:
  - the palette still leaned too warm and ivory-heavy
  - the pages had the right structure, but not enough of the original product voice and motion
- Confirmed we could introduce Alpine progressively, without changing backend behavior, by using it for disclosure and browsing controls.

### Changed
- Updated [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css) to push the design further toward the original product rhythm:
  - cooler blue-gray page backgrounds
  - stronger navy heading treatment
  - more saturated blue/orange accent use
  - less ivory-heavy surface treatment
  - voice-oriented utility classes like `voice-line`
- Added Alpine via [templates/base.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/base.html) using the CDN build so lightweight interaction is now available repo-wide.
- Strengthened product voice and rhythm in:
  - [templates/public/landing.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/landing.html)
  - [templates/public/discover.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/discover.html)
  - [templates/admin/detail.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/detail.html)
- Added Alpine-powered interaction polish:
  - discover filter visibility toggle
  - discover featured-card emphasis toggle
  - entity detail extended-details toggle
  - entity detail tag expansion toggle

### Decisions
- Use Alpine only for progressive disclosure and small interaction improvements, not as the basis for a client-heavy frontend.
- Keep the stronger product voice concentrated in public browse/storytelling areas first, while letting admin surfaces absorb it more gradually.

### Why
- This brings the rebuilt app noticeably closer to the original product’s energy without falling back into the old dependency stack.
- It also proves that we can add motion and interactivity in a controlled way that still fits server-rendered Flask pages.

### Verification
- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy app tests`

### Notes for the next session
- The app now has:
  - a stronger blue/gray/orange palette
  - more product voice in public browse surfaces
  - the first Alpine-powered interaction layer
- The next likely step is either:
  - entity-specific storytelling sections, such as related records and curated supporting context, or
  - Alpine enhancements for search/discover filters, saved views, and richer card transitions.

## 2026-03-31 (Closer To Original Design Language)

### Investigated
- Compared the current refreshed templates directly against:
  - the old `explor_alpha` template set
  - the local `design_drafts/` folder
- Identified that the biggest remaining gap was not only copy or palette, but the old product’s more image-led, atmospheric page rhythm.

### Changed
- Copied owned draft imagery from `design_drafts/` into the current repo’s static tree:
  - [static/images/discovery.jpg](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/images/discovery.jpg)
  - [static/images/east-ride.jpg](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/images/east-ride.jpg)
  - [static/images/grid-1.jpg](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/images/grid-1.jpg)
  - [static/images/things-1.jpg](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/images/things-1.jpg)
- Expanded [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css) with media-driven presentation primitives such as:
  - `media-strip`
  - `media-frame`
  - `media-frame-copy`
- Updated [templates/public/landing.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/landing.html) with a stronger media-led strip and more product-voice-forward section language.
- Updated [templates/public/discover.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/discover.html) with more of the original “Now / Next” browse rhythm.

### Decisions
- Reuse owned draft imagery where it helps recover the original product feel.
- Keep using those assets as composition and mood anchors, not as a reason to reintroduce the old dependency stack.

### Why
- The original product language was as much about atmosphere and pacing as it was about color or layout.
- Pulling in some of the draft imagery helps the rebuilt app feel less abstract and closer to the earlier brand intent.

### Verification
- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy app tests`

### Notes for the next session
- The app is now materially closer to the original design language in:
  - palette
  - product voice
  - image use
  - browse rhythm
- The next likely step is entity-specific storytelling with related-record strips, image-led highlights, and per-entity supporting context blocks.

## 2026-03-31 (Route And Segment Detail Depth)

### Investigated
- Compared the current generic admin detail surface with the older route detail patterns from `explor_alpha`.
- Reviewed the current `Route` and `Segment` models to see which fields and relations were still missing from the browser detail pages.
- Confirmed the shared detail template could carry a richer story-plus-inventory layout without splitting into a separate legacy template family.

### Changed
- Expanded the route detail handler in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) to surface substantially more route metadata:
  - privacy, source identifiers, creator and athlete context
  - start and end coordinates
  - elevation profile and geometry fields
  - created and updated timestamps
  - counts for linked groups, segments, and external links
- Expanded the segment detail handler in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) to show fuller segment data:
  - elevation loss, high and low points
  - source URL
  - track hash and max speed
  - geometry fields
  - record, create, and update timestamps
  - linked route and image counts
- Added route and segment-specific story sections, media previews, and connected-record collections in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py).
- Updated the shared detail template in [templates/admin/detail.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/detail.html) so entity pages can render:
  - narrative story cards
  - richer metric-first detail inventories
  - connected record sections for related groups, routes, segments, links, and images
- Added supporting styles in [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css) for the new story and related-record layouts.
- Extended [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) with richer route detail coverage and a new full-record segment detail test.

### Decisions
- Keep the richer detail experience inside the shared `admin/detail.html` surface rather than rebuilding old entity-specific templates one by one.
- Port the old product rhythm as structure and emphasis:
  - story first
  - stats next
  - full factual inventory after that
  - connected records nearby
- Prefer Alpine-backed progressive disclosure and repo-local CSS primitives over reviving the old Bootstrap and jQuery implementation.

### Why
- Routes and segments are the records most likely to feel incomplete if they only show a handful of fields.
- The old product was strongest when a detail page combined meaning, effort, and context instead of acting like a flat dump of attributes.
- Reusing the shared detail surface keeps the codebase lighter while still moving much closer to the original complete-record feel.

### Verification
- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy app tests`

### Notes for the next session
- Route and segment pages now expose a much fuller data inventory and feel materially closer to the older product’s depth.
- The next strongest continuation would be the same treatment for other entity detail pages that still feel thin, especially events, points of interest, and activity records.

## 2026-03-31 (Event, POI, And Activity Detail Depth)

### Investigated
- Reviewed the remaining detail routes for `Event`, `PointOfInterest`, and `Activity` after enriching routes and segments.
- Compared each page’s current field coverage against the underlying model shape and related records already available in the database.
- Confirmed the same shared detail template could carry these richer pages without introducing another round of entity-specific templates.

### Changed
- Expanded the event detail handler in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) to surface:
  - schedule and duration fields
  - privacy, contact, registration, and location metadata
  - timestamps and geometry context
  - richer media previews
  - related route, activity, calendars, fees, and participants
- Expanded the point-of-interest detail handler in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) to show:
  - coordinate and geometry context
  - creation and update timestamps
  - media previews from linked images
  - a more explicit story about why the waypoint matters
- Expanded the activity detail handler in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) to include:
  - fuller effort and timing metrics
  - source identifiers
  - start and end coordinates
  - geometry fields and timestamps
  - related route and image context
- Added new story-section and related-section helpers in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) for events, points of interest, and activities.
- Extended [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) with full-record detail coverage for:
  - events
  - points of interest
  - activities

### Decisions
- Continue treating “stronger detail pages” as a shared system problem, not as a prompt to rebuild old one-off templates.
- Prefer graceful non-linked related cards when a related entity does not yet have its own browser detail endpoint, instead of inventing broken navigation.

### Why
- After routes and segments, these were the most visible remaining detail pages that still felt like thin inspectors instead of product surfaces.
- Carrying the same pattern across entity types makes the admin experience feel coherent and closer to the original product’s depth.

### Verification
- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy app tests`

### Notes for the next session
- The richer detail treatment now covers routes, segments, events, points of interest, and activities.
- The next likely step is stronger route and activity media/map storytelling or filling in missing related-entity browser surfaces such as calendars.

## 2026-04-01 (Route And Activity Map/Elevation Storytelling)

### Investigated
- Reviewed the stored geometry and elevation fields already available on `Route` and `Activity`.
- Confirmed the app already stores line data as GeoJSON-like text through the geometry helpers, which made lightweight SVG rendering feasible without pulling in a new frontend map stack.
- Checked the shared detail template and design system to confirm there was enough room to add a dedicated Explor-specific visual section.

### Changed
- Added server-side geometry and elevation helpers in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) to generate:
  - simplified SVG route traces
  - compact elevation profiles
  - lightweight visual-section payloads for detail templates
- Updated the route detail page in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) to surface a dedicated Explor visual section using stored line geometry and elevation arrays.
- Updated the activity detail page in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) to show a recorded trace and a compact climbing profile based on available elevation markers.
- Expanded [templates/admin/detail.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/detail.html) with an `Explor View` section that:
  - gives maps and profiles their own first-class space
  - uses Alpine for simple view toggling when more than one visual is available
- Added the styling for these visual cards in [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css), keeping the look aligned with the stronger blue/gray/orange design direction.
- Extended [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) so route and activity detail tests now assert the presence of the new Explor map/elevation surfaces.

### Decisions
- Prefer server-rendered SVG visuals over reintroducing a client-heavy map/chart library for this stage.
- Treat maps and elevation as authored storytelling surfaces, not just extra raw fields appended lower on the page.

### Why
- Maps and elevation are central to the Explor product feel, especially on routes and activities.
- This approach gets that experience materially closer to the original product language while keeping the implementation lightweight, testable, and consistent with the current server-rendered stack.

### Verification
- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy app tests`

### Notes for the next session
- Route and activity pages now have first-class map/elevation storytelling instead of only raw geometry/elevation fields.
- The next likely step is either:
  - stronger segment-specific elevation/map treatment, or
  - a browser detail surface for calendars so event related-record sections can become fully navigable.

## 2026-04-01 (Route And Segment Interactive Map/Elevation)

### Investigated
- Compared the original route detail experience in `explor_alpha/app/templates/routes/` with the current rebuilt detail page.
- Reviewed the legacy route page scripts to isolate the high-value behaviors:
  - map-first route presentation
  - a dedicated elevation chart on the detail page
  - quick switching between simplified and fuller route geometry
- Confirmed the current stored geometry and elevation fields were already sufficient to recreate those interactions without reintroducing the full old Leaflet and Highcharts stack.

### Changed
- Extended the route and segment detail handlers in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) so both now provide richer `visual_sections`.
- Added geometry sampling and SVG helper logic in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) to support:
  - summary and full-track line views
  - sampled hover targets for map readouts
  - richer elevation profile samples
- Updated [templates/admin/detail.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/detail.html) so map visual sections now support:
  - summary versus full-track switching
  - hoverable route and segment sample chips
  - richer elevation hover targets and profile readouts
- Expanded [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css) with styling for:
  - map/profile interaction chips
  - layered visual toggles
  - interactive highlight states
- Extended [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) so route and segment detail coverage now asserts the new map/elevation surfaces.

### Decisions
- Recreate the original interaction priorities with server-rendered SVG and Alpine instead of restoring the old dependency-heavy implementation directly.
- Treat summary/full-track switching and hoverable map/profile affordances as the most valuable parts of the old route experience to port first.

### Why
- Maps and elevation are central to the Explor product feel, especially on routes and segments.
- This gets much closer to the original route detail rhythm while staying aligned with the current repo-local design system and lighter frontend stack.

### Verification
- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy app tests`

### Notes for the next session
- Route and segment detail pages now both carry a more recognizably Explor-style map/elevation experience.
- The next strongest step would be adding calendar detail pages and then tightening route/event/share-related interaction flows around those richer destinations.

## 2026-04-01 (Leaflet And Original Elevation Behavior)

### Investigated
- Re-read the original route detail implementation in `explor_alpha`, especially:
  - [routes_details.html](/Users/bheliker/Documents/_Projects/explor/explor_alpha/app/templates/routes/routes_details.html)
  - `app/static/js/elevation.js`
  - the inline Leaflet map initialization used on the old route page
- Confirmed that the SVG approximation added earlier was a useful intermediate step, but not a correct substitute for a true geographic map.

### Changed
- Updated [templates/base.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/base.html) to support page-specific head and script blocks so richer detail pages can load the right frontend assets cleanly.
- Reworked [templates/admin/detail.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/detail.html) so route, segment, and activity visual sections now mount:
  - true Leaflet map containers
  - Highcharts-based elevation containers
  - summary/full-track layer toggles on map views
- Added [static/js/detail_visuals.js](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/js/detail_visuals.js) to initialize:
  - Leaflet maps using the original Mapbox basemap style URL
  - start markers via `L.divIcon`
  - Highcharts elevation charts using options closely modeled on the original `elevationChartDetailsPage(...)`
- Updated [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) so map visual sections now provide real geographic `latlng` layers instead of only SVG approximations.
- Refined [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css) for Leaflet container presentation, map markers, and chart framing.
- Extended [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) coverage while preserving green server-side verification.

### Decisions
- Use Leaflet for geographic route and segment maps, matching the original product behavior more directly.
- Keep the rebuilt app’s structure and design system, but port the original mapping and elevation primitives much more literally where they are core to product identity.

### Why
- A route detail page needs to show real geography, not an abstract x/y trace.
- The original route detail experience was defined by actual map context plus an elevation chart; this restores that priority while staying inside the rebuilt Flask template architecture.

### Verification
- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy app tests`

### Notes for the next session
- Route and segment pages now use real Leaflet maps and original-style elevation charts rather than the earlier SVG placeholder treatment.
- The next likely step is tightening share/export/calendar flows around these richer route destinations, or carrying similar basemap treatment into other map-first records where it matters.

## 2026-04-01 (Archive Import Into Current Local Postgres)

### Investigated
- Confirmed the archived backup at [db_archive/terminal_backup_20230531.sql](/Users/bheliker/Documents/_Projects/explor/explor_codex/db_archive/terminal_backup_20230531.sql) is a PostgreSQL custom-format dump, not plain SQL.
- Restored that archive into a temporary local comparison database `explor_archive` to inspect the old schema directly instead of guessing from the dump.
- Compared the restored archive schema with the current app schema and identified the main compatibility points:
  - core entities still align closely
  - `external_urls` now maps to `group_external_url`
  - old group roles include `Lead` and `Invited`, which no longer exist in the current canonical lookup table
  - old archive-only tables like payments, followers, roles, posts, and subscribers should not be imported into the current app schema

### Changed
- Reused the existing local `explor` PostGIS database as the import target after truncating the disposable app data already present there.
- Restored the archive into a sidecar local database `explor_archive` for inspection and import planning.
- Added an import utility at [scripts/import_archive_to_current.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/scripts/import_archive_to_current.py) that:
  - copies compatible archive data into the current schema in dependency order
  - converts legacy array fields into the current JSON-backed columns
  - preserves geometry via `ST_AsEWKT(...)` / `ST_GeomFromEWKT(...)`
  - remaps legacy group roles (`Lead -> admin`, `Invited -> pending`)
  - maps `external_urls` into `group_external_url`
  - rebuilds `search_document` after the import
- Ran the import successfully into the current local `explor` database.

### Decisions
- Keep `explor` as the app-facing target database and use `explor_archive` only as a local restored reference database.
- Prefer a repeatable repo-local import script over one-off `pg_restore` experiments directly into the current schema.
- Import only the parts of the 2023 archive that still have a clear place in the current app model, rather than trying to recreate removed legacy product areas.

### Why
- The current schema has evolved enough that a blind restore into `explor` would be fragile and harder to repeat.
- A dedicated import script gives us a path we can rerun after future schema changes or when we need a fresh local dataset again.
- Rebuilding `search_document` immediately makes the imported data visible in the current admin/search surfaces without extra manual repair work.

### Verification
- Verified local target counts after import:
  - `user`: 66
  - `group`: 2328
  - `calendar`: 2468
  - `route`: 54637
  - `segment`: 60662
  - `event`: 240
  - `membership`: 2476
  - `image`: 37156
  - `group_external_url`: 573
  - `search_document`: 117867
- Verified `search_document` contains imported entity types for `group`, `route`, `segment`, and `event`.
- `uv run pytest`
- `uv run ruff check scripts/import_archive_to_current.py`
- `uv run mypy app tests scripts/import_archive_to_current.py`

### Notes for the next session
- The local app database now contains substantial real archived data and search has been rebuilt on top of it.
- The remaining import gaps are the archive-only legacy areas that no longer map cleanly into the current app model.
- A good next step is browsing the admin UI against the imported dataset to spot rendering, pagination, or query hot spots that only show up at real-data scale.

## 2026-04-01 (Palette Preview)

### Investigated
- Reviewed the current public/admin UI structure and confirmed the design tokens already live in [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css).
- Checked the base template, public route patterns, and route-test style before adding a new preview surface.

### Changed
- Added a public palette preview route at [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) that exposes the current color and non-color tokens to a template.
- Added [templates/public/palette.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/palette.html) to render labeled swatches in a table plus the supporting non-color token list.
- Extended [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css) with palette-table and swatch styles.
- Added a top-level nav link in [templates/base.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/base.html) so the preview is easy to reach.
- Added route coverage in [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py).

### Decisions
- Keep the preview as a public server-rendered page instead of a one-off static file so it stays close to the current design system.
- Show transparent colors on a checkerboard field to make alpha-based tokens easier to compare.

### Why
- This gives a quick, repeatable way to inspect the active palette without digging through CSS.
- Keeping the preview inside the app makes it easier to reuse during ongoing UI iteration.

### Verification
- `uv run ruff format .`
- `uv run ruff check .`
- `uv run mypy app tests`
- `uv run pytest`

## 2026-04-01 (Geo Index Audit And Backfill)

### Investigated
- Audited the imported local PostgreSQL dataset after the archive import to measure where real scale now exists:
  - `route`: 54,637
  - `segment`: 60,662
  - `image`: 37,156
  - `search_document`: 117,867
- Queried PostgreSQL index metadata and `pg_stat_user_tables` to see which tables were still relying on primary keys alone.
- Ran `EXPLAIN (ANALYZE, BUFFERS)` against representative queries from the current app:
  - recent search documents
  - tokenized search over `search_document`
  - image lookups by `segment_id`
- Checked geometry coverage in the imported data and found:
  - route and segment geometry is broadly populated
  - group and event point geometry is partially populated
  - image `geoll` was empty even though `latlng` existed on most imported image rows

### Changed
- Added [migrations/versions/0d7f4ee1d1fa_add_geo_and_search_indexes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/migrations/versions/0d7f4ee1d1fa_add_geo_and_search_indexes.py).
- Added btree indexes for the most-used foreign key and join paths, including:
  - `image.segment_id`, `image.group_id`, `image.activity_id`, `image.photographer_id`
  - `event.owner_id`, `event.route_id`, `event.activity_id`, `event.date_start`
  - `activity.athlete_id`, `activity.route_id`
  - `calendar.group_id`
  - `group.admin_id`, `group.hero_photo_id`
  - `group_external_url.owner`, `group_external_url.route_id`
  - `group_dues.owner`
  - `event_fee.event`
  - reverse-side indexes for join tables such as `route_segments.segments`, `group_routes.route`, `calendar_events.events`, `event_images.image`, `poi_images.image`, and `event_attendance.attendance`
- Added a regular index on `search_document.updated_at` to support the “recent search docs” surfaces.
- Added a PostgreSQL trigram GIN index on `lower(search_text)` for the current portable search implementation.
- Added PostgreSQL GiST indexes for the most useful populated spatial columns:
  - `group.geoll`
  - `event.geoll`
  - `points_of_interest.geoll`
  - `image.geoll`
  - `route.summary_polyline`
  - `segment.summary_polyline`
  - `activity.summary_polyline`
- Backfilled missing geometry where the imported dataset already had coordinates:
  - `image.geoll` from `image.latlng`
  - `group.geoll` from `group.home_latlng`
  - `event.geoll` from `event.lon` / `event.lat`

### Decisions
- Keep the current cross-database search architecture, but optimize PostgreSQL with trigram indexing instead of reviving legacy `tsvector` columns.
- Index `summary_polyline` rather than `full_track` for the main spatial browsing path.
- Prefer partial GiST indexes on populated geometry columns instead of broader indexes on every geometry field.
- Use the imported dataset itself to drive optimization work rather than guessing from the schema alone.

### Why
- The imported archive has pushed the app into a scale where sequential scans are now visible in normal UI paths.
- The current admin and public search surfaces rely heavily on `search_document`, so it was the most immediate win.
- Browsing and nearby-style geographic work should center on summary geometry and point geometry first, because those are the fields most likely to support real UI interactions without unnecessary index weight.
- The image backfill materially increases the amount of usable geographic data without changing the public API shape.

### Verification
- Migration verification:
  - `DATABASE_URL=sqlite+pysqlite:////Users/bheliker/Documents/_Projects/explor/explor_codex/.codex-tmp/migration-dbs/geo-index-audit.db UV_CACHE_DIR=/Users/bheliker/Documents/_Projects/explor/explor_codex/.codex-tmp/uv-cache uv run flask --app 'app:create_app()' db upgrade`
  - `uv run flask --app 'app:create_app()' db upgrade`
- Query-plan spot checks after the migration:
  - recent `search_document` lookup dropped from a parallel seq scan to an index scan on `updated_at`
  - tokenized search now uses the trigram GIN index instead of a full table scan
  - image lookup by `segment_id` now uses `ix_image_segment_id`
  - nearby image lookup uses `ix_image_geoll_gist`
- Data coverage after backfill:
  - `group.geoll`: 2,318 populated
  - `event.geoll`: 147 populated
  - `image.geoll`: 34,618 populated
- `uv run ruff check .`
- `uv run mypy app tests scripts/import_archive_to_current.py`
- `uv run pytest`

### Notes for the next session
- The database now has a much stronger baseline for search, spatial lookups, and related-record joins against the imported archive-scale dataset.
- The next strongest geography-focused step would be to add explicit nearby/bounding-box query helpers and surface them in either the API or the admin UI.
- A separate auth/admin concern still exists: verify that non-admin users truly cannot reach admin/write paths in the running environment and tighten that if needed.

## 2026-04-01 (Route Map Debugging)

### Investigated
- Followed up on the new Leaflet detail-page maps after the elevation renderer moved to a repo-local SVG implementation.
- Verified that route visual payloads were producing real `latlngs` arrays from stored `summary_polyline` and `full_track` geometry.
- Confirmed that some imported records have degenerate summary geometry with repeated points, which can make the default map layer look like a single-point route.

### Changed
- Moved the detail-page map JSON config mount outside the Leaflet container in [templates/admin/detail.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/detail.html).
- Hardened [static/js/detail_visuals.js](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/js/detail_visuals.js) so map initialization now:
  - looks up config by explicit `data-map-target`
  - prefers the first layer with visible geographic distance instead of blindly selecting the first layer
  - re-invalidates and re-fits the map after mount so the route line has a better chance to render correctly on first paint

### Decisions
- Keep the current lightweight Leaflet path, but make it resilient to messy imported geometry instead of assuming every summary line is valid.
- Preserve the current repo-local elevation renderer while focusing map work on geographic correctness and original route-page behavior.

### Why
- The original Explor route experience depends on the route line itself being the hero, not just the trailhead marker.
- Imported real-world geometry is noisy enough that the client should actively avoid collapsed or placeholder linework when picking a default map layer.

### Verification
- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy app tests`

### Notes for the next session
- If any detail pages still show marker-only behavior, inspect those records for geometry variants such as `FeatureCollection`, `MultiLineString`, or malformed imported coordinate payloads and expand the parser accordingly.

## 2026-04-01 (Segment Detail Layout Fix)

### Investigated
- Followed up on a segment-detail CSS defect where the right-hand value column could overlap the left-hand label column.
- Narrowed the problem to shared detail/story row layout rather than segment-specific data or template structure.

### Changed
- Updated [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css) so detail-page grid children can shrink correctly and long story-row values wrap instead of overrunning adjacent content.

### Decisions
- Fix this in the shared detail layout primitives instead of adding a one-off segment-only override.

### Why
- Segment pages naturally surface long coordinate and metadata values, so they expose layout assumptions that should be resilient across all entity detail pages.

### Verification
- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy app tests`

## 2026-04-02 (Event Maps, Calendar Maps, And Stats Bar)

### Investigated
- Reviewed the original `explor_alpha` route detail page and its `statsBar` treatment to recover the icon-led rhythm around rating, distance, duration, elevation, and grade.
- Traced the old `user_units(...)` helper and confirmed the older app used a real `current_user.units` preference rather than inferring units from tags.
- Audited the current detail surfaces and confirmed events had no geographic visual section yet, while calendars lacked a detail route entirely.

### Changed
- Added an explicit `User.units` preference with migration support in:
  - [app/models/user.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/models/user.py)
  - [app/services/users.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/services/users.py)
  - [migrations/versions/f24d3d3b9c1a_add_user_units_preference.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/migrations/versions/f24d3d3b9c1a_add_user_units_preference.py)
- Updated account and admin user flows so metric vs imperial preferences can be viewed and edited:
  - [app/auth.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/auth.py)
  - [templates/auth/account.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/account.html)
  - [templates/auth/account_edit.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/auth/account_edit.html)
  - [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py)
- Added shared stats-bar helpers and rendering so route, segment, activity, and event detail pages now show the old-style icon-led metric strip with unit-aware values.
- Generalized the Leaflet detail renderer in [static/js/detail_visuals.js](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/js/detail_visuals.js) so a map layer can now render:
  - multiple polylines
  - marker collections
  - mixed marker-plus-route layers
- Added map-first event and calendar detail surfaces in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py), including:
  - event footprint layers for event point + linked route/activity context
  - calendar footprint layers for event markers + route network context
  - a new calendar collection/detail route path
- Updated [templates/admin/detail.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/admin/detail.html) and [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css) to render the stats bar and keep the geographic treatment visually consistent with the route pages.
- Added regression coverage in [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) for:
  - account units persistence
  - route stats-bar rendering
  - event geographic detail rendering
  - calendar map-first detail rendering

### Decisions
- Reintroduced unit preference as a first-class user setting instead of encoding it indirectly in `preference_tags`.
- Kept the geographic treatment inside the existing server-rendered detail flow by extending the shared Leaflet payload model instead of creating separate one-off map implementations for events and calendars.
- Used a heuristic for distance display so the current mixed fixture/data reality remains readable:
  - large values are treated as meters and converted
  - smaller values are treated as already being in kilometer-scale units

### Why
- The old product voice came not only from copy and color, but from how quickly a record surfaced the metrics riders actually scan first.
- Events and calendars are central coordination surfaces in Explor; they need the same spatial clarity as routes for the experience to feel coherent again.
- Explicit user unit preference is the cleanest way to make metric display trustworthy across the app.

### Verification
- Migration verification:
  - `UV_CACHE_DIR=/Users/bheliker/Documents/_Projects/explor/explor_codex/.codex-tmp/uv-cache DATABASE_URL=sqlite+pysqlite:////Users/bheliker/Documents/_Projects/explor/explor_codex/.codex-tmp/migration-dbs/event_map_statsbar.db uv run flask --app 'app:create_app()' db upgrade`
- `uv run ruff check .`
- `uv run mypy app tests`
- `uv run pytest`

### Notes for the next session
- The next strongest continuation is public-facing event/calendar discovery so these richer spatial surfaces are reachable outside admin.
- If we want to get even closer to the original experience, the next layer is richer calendar/event map interactions such as marker summaries, day-based filtering, and route/event combined browse modes.

## 2026-04-07 (Routes And Segments Browser Foundations)

### Investigated
- Reviewed the original `explor_alpha` routes page to recover the key interaction model:
  left-side browsing controls plus a synchronized map on the right.
- Checked the rebuilt app for the current public design language, available route and segment data, and existing relationships to groups, segments, and events.
- Confirmed the rebuilt backend already had enough route and segment fields to support a real first-pass browse surface without introducing new persistence work.

### Changed
- Added public browse pages for:
  - `/routes`
  - `/segments`
- Added a shared public browser template at [templates/public/entity_browser.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/entity_browser.html).
- Added client-side browse interactions in [static/js/collection_browser.js](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/js/collection_browser.js):
  - search
  - grid/list toggle
  - favorites-first ordering
  - sort by closest, length, elevation, or duration
  - live map-area filtering
  - map recentering and reset/search-area controls
- Added route-side page data helpers in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) to prepare:
  - route browser cards
  - segment browser cards
  - event counts for routes
  - summary stats
  - map-ready bounds and focus data
- Updated [templates/base.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/base.html) navigation to surface the new routes and segments entry points.
- Extended [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css) with the new public browser layout and map styling.
- Added public page coverage in [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py).

### Decisions
- Start with a map-synchronized browser foundation before rebuilding true tile-map behavior or server-backed viewport queries.
- Keep the first pass dependency-light by rendering a stylized coordinate map with Alpine-driven filtering rather than pulling in a heavy remote map stack immediately.
- Treat favorite ordering as tag-driven for now using tags such as `favorite`, `featured`, `saved`, `starred`, and `classic`.
- Fall back from “closest to me” to the current map focus when a signed-in user does not have a stored home point.

### Why
- These pages are the most important navigation surface in the product, so it was more valuable to re-establish the browsing rhythm and interaction contract than to wait for a perfect final map implementation.
- The shared browser template creates one reusable pattern for routes and segments while keeping room for richer filtering and real map providers later.
- The current implementation gives us a meaningful product-facing foundation now and a clean place to evolve map-backed search behavior next.

### Verification
- `uv run pytest`
- `uv run ruff check .`
- `uv run ruff format --check app tests`
- `uv run mypy app tests`

### Notes for the next session
- The new pages are interaction-rich and fully tested, but the map is still a stylized rebuilt browse canvas rather than a full geographic tile map.
- A strong next step would be adding:
  - real map tiles and geometry rendering
  - server-backed viewport filtering
  - richer filters for clubs, events, terrain, and saved/followed state

## 2026-04-07 (Routes Browser Payload Cap)

### Investigated
- Reproduced a browser lockup on `/routes` after the first public browser pass landed.
- Measured the response shape against the imported dataset and confirmed the page was trying to inline tens of thousands of route records and geometries at once.
- Verified the rendered `/routes` payload had grown into the 95+ MB range, which was enough to make the browser fail to open the page.

### Changed
- Added a hard public browser request cap of `20` records per request in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py).
- Switched the public route and segment pages to query only the capped slice instead of loading every record in the database into the page payload.
- Updated [templates/public/entity_browser.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/entity_browser.html) to clearly show that the page is only rendering up to the capped number of records.
- Added regression coverage in [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) proving the `/routes` page does not emit more than 20 records.

### Why
- The interactive browser can only be useful if it opens reliably; limiting the initial slice is more important than pretending to show the full catalog inside one HTML response.
- This preserves the new browsing surface while we design a better long-term strategy for paginated or server-backed map exploration.

### Verification
- `uv run pytest tests/test_app.py -k 'public_routes_route or public_segments_route'`
- `uv run ruff check app/routes.py tests/test_app.py`

## 2026-04-08 (Browse Card And Discover CTA Polish)

### Investigated
- Followed up on public browse-page polish after the route and segment browser merge.
- Confirmed the remaining gaps were mostly presentation and access cues:
  - card titles did not surface the existing detail destination clearly
  - image-backed cards were not using available route or segment imagery
  - viewport copy added noise without helping navigation
  - non-admin users could still see the palette entry point
  - long route and segment descriptions needed a tighter preview limit
  - logged-in users were still being prompted to log in again from discover surfaces

### Changed
- Updated [templates/public/entity_browser.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/entity_browser.html) so browser card titles link to the existing detail URL when present and grid cards can render a background image.
- Added browser image helpers and description-preview truncation in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py), including a hard cap that keeps route and segment previews at roughly 200 characters.
- Updated [static/js/collection_browser.js](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/js/collection_browser.js) and [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css) for image-backed browser cards and cleaner map/list presentation.
- Removed the viewport-size readout from the public route and segment browser.
- Hid the `Palette` navigation link from non-admin users in [templates/base.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/base.html).
- Updated [templates/public/discover.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/discover.html) so authenticated users no longer see `Log in for deeper access` or `Log in to inspect`.
- Added regression coverage in [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) for admin card linking/image rendering, authenticated discover behavior, palette visibility, and description truncation.

### Why
- These changes make the main browse surfaces feel more product-like and less noisy while avoiding contradictory prompts for users who are already signed in.
- Tight preview limits and visual cards make scanning faster without losing the path into deeper record detail.

### Verification
- `uv run pytest tests/test_app.py -k 'public_discover_route or public_routes_route or public_segments_route or public_route_browser_shows_linked_title_and_card_image_for_admin or public_route_browser_truncates_long_description or palette_link_hidden_for_non_admin'`
- `uv run ruff check app/routes.py tests/test_app.py`
- `uv run mypy app tests`

## 2026-04-08 (Public Route And Segment Detail Links)

### Investigated
- Rechecked why route and segment browse card titles still were not clickable for regular users.
- Confirmed the template wiring was fine, but the public browser payload only emitted `detailUrl` for admins because no public route or segment detail page existed yet.
- Reviewed the original `explor_alpha` route browser template to borrow more of the image-first card feel from the earlier grid/list view.

### Changed
- Added public detail pages at [templates/public/detail.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/detail.html) backed by:
  - [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) `GET /routes/<id>`
  - [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) `GET /segments/<id>`
- Updated public detail URL generation in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) so:
  - public users get route and segment detail links
  - admins still keep admin detail destinations where available
- Added public related-section helpers in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) so connected routes and segments can cross-link on the new public detail pages.
- Updated [templates/public/entity_browser.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/entity_browser.html) so title links are consistent in both grid and list views.
- Adjusted [static/js/collection_browser.js](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/js/collection_browser.js) and [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css) so image-backed cards use a stronger CSS gradient overlay rather than a weak inline fade, closer to the original browse treatment.
- Extended [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) for:
  - anonymous route title links
  - public route detail rendering
  - public segment detail rendering
  - discover results linking into public route detail pages

### Why
- The route and segment browser is one of the primary navigation surfaces, so cards need a real next click for public users instead of visual affordances that only work for admins.
- The stronger image fade keeps card text legible while recovering more of the original browse-page mood.

### Verification
- `uv run pytest tests/test_app.py -k 'public_discover_route or public_routes_route or public_segments_route or public_route_browser_shows_linked_title_and_card_image_for_admin or public_route_browser_links_titles_for_signed_out_users or public_route_detail_route_renders or public_segment_detail_route_renders or public_route_browser_truncates_long_description or palette_link_hidden_for_non_admin'`
- `uv run ruff check app/routes.py tests/test_app.py`
- `uv run mypy app tests`
- `uv run mypy app tests`

## 2026-04-07 (Leaflet Browse API And Rich Filters)

### Investigated
- Continued the public routes and segments browser work after the summary-polyline optimization.
- Reviewed the existing detail-page Leaflet implementation so the public map could reuse the same tile-map direction instead of inventing a second mapping stack.
- Confirmed the next bottleneck was architectural rather than payload-only: the page needed server-backed viewport queries and real map-driven loading rather than larger inline page state.

### Changed
- Added dedicated public browse APIs in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py):
  - `GET /api/browser/routes`
  - `GET /api/browser/segments`
- Moved the public browser query logic into shared server-side bundle helpers that now support:
  - map viewport bounding box filters
  - closest/length/elevation/duration sort
  - favorites-only filtering
  - club filtering
  - event-linked filtering
  - terrain filtering
- Switched the public `/routes` and `/segments` pages to pass API/bootstrap config instead of acting as the full data transport.
- Upgraded [templates/public/entity_browser.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/entity_browser.html) to include:
  - real Leaflet tile-map assets
  - club filter control
  - terrain filter control
  - event-linked filter control
- Replaced the old SVG map client in [static/js/collection_browser.js](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/js/collection_browser.js) with a Leaflet-backed browser that:
  - renders raster tiles
  - redraws lines and markers from API results
  - refetches server-backed results on move/zoom and filter changes
- Updated [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css) for the new Leaflet map surface and public browser filter layout.
- Added API and page coverage in [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) for:
  - route browse API filtering by viewport + club + events + terrain
  - segment browse API filtering by viewport + club + events + terrain

### Decisions
- Keep the public browser limited to 20 loaded records at a time, but make that slice server-backed and spatially meaningful.
- Reuse the same Carto raster tile direction already used in the detail-map work so the public and admin map language stay aligned.
- Treat club and event filters as first-class server-side constraints instead of client-only post-processing.

### Why
- This gets the main navigation pages much closer to the original product behavior: the map is now real, and the list is driven by where the map is and what the rider is filtering for.
- The browser API gives us a stable place to add future pagination, clustering, or recommendation logic without pushing huge serialized payloads back into the page HTML.

### Verification
- `uv run pytest`
- `uv run ruff check .`
- `uv run ruff format --check app tests`
- `uv run mypy app tests`

### Notes for the next session
- The main remaining gap is deeper exploration beyond the first 20 records in the current server slice.
- The next strongest continuation would be one of:
  - incremental viewport pagination
  - marker clustering
  - richer event/club preview cards and popup summaries

## 2026-04-07 (Browser Pagination And Map/List Sync Refinement)

### Investigated
- Continued polishing the new map-backed public browser after the Leaflet + browse API milestone.
- Focused on two usability gaps that still made the experience feel early:
  - limited exploration past the first 20 loaded records
  - weak feedback between the list and the map

### Changed
- Added server-backed offset pagination to the public browser APIs in [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py).
- Extended route and segment browser payloads with lightweight related previews so the map can show more useful summaries without extra requests.
- Updated [static/js/collection_browser.js](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/js/collection_browser.js) so the browser now supports:
  - previous/next 20 paging
  - selected-item state shared between map and list
  - Leaflet marker popups with richer summaries
  - fit-loaded-results map recentering
  - pagination reset when filters or search terms change
- Updated [templates/public/entity_browser.html](/Users/bheliker/Documents/_Projects/explor/explor_codex/templates/public/entity_browser.html) with:
  - previous/next controls
  - fit-results control
  - selected-card styling hooks
- Updated [static/css/admin.css](/Users/bheliker/Documents/_Projects/explor/explor_codex/static/css/admin.css) for:
  - selected result styling
  - popup card styling
  - pagination row layout
- Added regression coverage in [tests/test_app.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/tests/test_app.py) for route browser offset pagination.

### Why
- The server-backed browser became meaningfully more usable once people could continue exploring beyond the first slice without changing the whole mental model.
- Stronger map/list sync and richer popups make the page feel less like raw filtering and more like a browse-first navigation product.

### Verification
- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy app tests`

### Notes for the next session
- The next strongest enhancement is marker clustering so dense route areas stay readable at wider zoom levels.
- Another strong follow-up is richer route/segment preview content in popups or side panels, especially event dates and club identity.

### Notes for the next session
- With the cap in place, the current `/routes` response dropped to roughly 160 KB in the imported dataset instead of tens of megabytes.
- The next meaningful improvement is real paginated or viewport-backed loading so the page can explore beyond the first 20 records without reintroducing giant inline payloads.

## 2026-04-07 (Public Browser Summary-Polyline Only)

### Investigated
- Followed up on continued slowness in `/routes` after the 20-record cap.
- Confirmed the public browser helpers still had `summary_polyline or full_track` fallback logic, and the ORM query shape was still loading full `Route` and `Segment` rows.

### Changed
- Updated [app/routes.py](/Users/bheliker/Documents/_Projects/explor/explor_codex/app/routes.py) so the public `/routes` and `/segments` browser queries now:
  - use `load_only(...)` to fetch the narrow browser field set
  - include `summary_polyline`
  - exclude `full_track`
- Removed the public browser fallback from `summary_polyline` to `full_track` for both route and segment map data and center calculations.

### Why
- Even with a record cap, the public browser should not pay the cost of loading heavyweight full-track geometry when the page only needs the lightweight summary line.

### Verification
- `uv run pytest tests/test_app.py -k 'public_routes_route or public_segments_route'`
- `uv run ruff check app/routes.py tests/test_app.py`
