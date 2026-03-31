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
