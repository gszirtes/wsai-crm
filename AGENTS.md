# AGENTS.md

Guidance for AI coding agents working in this repository. (See [CLAUDE.md](CLAUDE.md) for the Claude Code-specific version — keep the two in sync; the content here is the source of truth.)

## Project

wespeak.ai CRM — self-hosted, mobile-first CRM for a small (5–10 user) AI consulting company. FastAPI + PostgreSQL backend, React 18 (CRA) frontend, bilingual EN/HU (i18next), AI command bar via OpenRouter. Runs as 3 Docker Compose services (`db`, `backend`, `frontend`) behind nginx on a single Hetzner box. See [README.md](README.md) for full feature scope and [DEPLOYMENT.md](DEPLOYMENT.md) for the production runbook.

## Setup & run

### Backend (from `backend/`)
```bash
pip install -r requirements.txt
export DATABASE_URL="postgresql+psycopg2://crm_user:change_me@localhost:5432/wespeak_crm"
export JWT_SECRET="dev-secret"
export FERNET_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
alembic upgrade head   # schema is Alembic-owned — the app no longer creates its own tables
python -c "from server import seed; seed()"   # one-time bootstrap: admin/demo users + sample data
uvicorn server:app --reload --port 8001
```

### Frontend (from `frontend/`)
```bash
npm install
REACT_APP_BACKEND_URL=http://localhost:8001 npm start
```

### Docker (full stack)
```bash
cp .env.example .env   # then fill in JWT_SECRET, FERNET_KEY, passwords
docker compose up -d --build
```

## Tests

The pytest suites are **integration tests that hit a live server** over HTTP (`requests`, `BASE_URL` from `REACT_APP_BACKEND_URL`, default `http://localhost:8001`) — there is no FastAPI `TestClient` / in-memory DB. Start and seed the backend first, then:
```bash
cd backend
export RATE_LIMITING_ENABLED=false   # avoid 429s from login-heavy test runs
pytest -v                            # all 49 tests (backend_test.py, test_iteration2.py, test_iteration3.py)
pytest tests/test_iteration3.py -v   # single suite
pytest tests/test_iteration3.py::TestNotifications -v   # single class
```
Tests log in as the seeded demo accounts (`admin@wespeak.ai` / `admin123`, etc. — see `backend/tests/conftest.py`), so a fresh/seeded DB is required. A session-scoped autouse fixture in `conftest.py` runs `alembic upgrade head` before any test (requires `DATABASE_URL` to be set in the test-running shell, pointing at the same DB the server under test uses).

There is no frontend test suite in active use (`npm test` runs CRA's default Jest runner but no test files exist beyond CRA's scaffold). There is no separate linter configured for either side beyond CRA's built-in ESLint.

## Architecture

**Auth**: email/password → bcrypt → JWT (`backend/auth.py`), access (12h) + refresh (7d), both in httpOnly cookies (`SameSite=Lax`, `Secure` gated by `COOKIE_SECURE`). Token is read from the cookie or an `Authorization: Bearer` header (`_extract_token`). Roles are a strict hierarchy in `ROLE_LEVELS`: `guest=0 < user=1 < manager=2 < admin=3`. Two dependencies gate endpoints: `require_role(min_role)` for level checks and `require_write` for the guest-is-read-only rule — apply both, not one, when a route needs both a floor role and write protection.

**Router pattern** (`backend/routers/*.py`, one file per entity, all registered in `server.py`): each router does its own SQLAlchemy queries directly against `models.py` (no repository/service layer), converts ORM objects to Pydantic `*Out` schemas via a local `_to_out()` helper (denormalizes things like `company_name` onto the output), and depends on `get_current_user` (read) or `require_write` (mutate). Delete handlers must manually null out or cascade child FKs before deleting a parent — see `contacts.py::delete_contact` for the pattern; DB-level `ondelete` rules in `models.py` are `SET NULL` for most optional FKs and `CASCADE` only for `TimeEntry`/`Notification`.

**AI command flow** (`backend/ai_service.py` + `routers/ai_router.py`): user free-form text → OpenRouter chat completion with a fixed system prompt requesting strict JSON (`{action, data, message}`) → backend validates `data` fields against the same enums used elsewhere (deal stage, contact status, etc.) before creating a record. The OpenRouter API key is stored encrypted (Fernet, `FERNET_KEY` env) in `AppSetting`, settable per-instance via the Settings page, falling back to `OPENROUTER_API_KEY` env.

**Data model** (`backend/models.py`): 10 tables, string UUID PKs (`gen_id()`). Core entities — `Company`, `Contact`, `Deal`, `Project`, `Activity` — all carry an `owner_id` (nullable FK to `User`, `SET NULL` on delete) and most enum-like fields (`status`, `stage`, `type`, `priority`) are plain strings validated only at the Pydantic layer (`schemas.py` uses `Literal[...]`) — the DB itself does not enforce the enum. `TimeEntry` belongs to a `Project` (CASCADE) and feeds billing via `Project.hourly_rate`; `backend/utils.py::logged_hours_for()` is the shared aggregation used wherever "hours logged" needs to be computed — reuse it instead of re-summing `TimeEntry`.

**Schema migrations**: Alembic-owned (`backend/alembic/`, config in `backend/alembic.ini` + `backend/alembic/env.py`). `env.py` reads `DATABASE_URL` from the environment (same var `database.py` uses) and targets `Base.metadata` from `models.py` — one env var drives both the app and its migrations. There is a single baseline revision covering the schema as of the CRM v2 migration's start; new schema changes get their own revision (`alembic revision --autogenerate -m "..."`) rather than hand-edited `ALTER TABLE` statements.

**Bootstrap sequence** (migrate → seed → serve): `alembic upgrade head` then `seed()` (`server.py`) run once, in that order, **before** uvicorn starts — in Docker via `backend/entrypoint.sh`, for local dev as two explicit commands (see Setup & run above), and in the test suite the migration step runs via an autouse session fixture in `backend/tests/conftest.py`. Neither step is a FastAPI startup hook: with `--workers 2`, a startup-event hook would run once per worker process and race itself (this is exactly what happened when `seed()` used to be wired to `@app.on_event("startup")` — two workers double-inserted the admin user). `seed()` itself seeds the admin account + 3 demo users + sample CRM data **only if they don't already exist** (admin password is not reset on restart) and is safe to call from a script (`python -c "from server import seed; seed()"`) since it does its own session-scoped DB work, not app startup.

**Frontend**: CRA (JS/JSX, not TS). `App.js` defines all routes wrapped in a `Protected` component that checks `useAuth()` and an optional `roles`/`adminOnly` prop — this is the only route-level RBAC; page components assume they're already authorized. `api.js` is a single shared axios instance (`withCredentials: true`, baseURL from `REACT_APP_BACKEND_URL`) — always import it rather than creating new axios instances, and use its `formatApiError()` for surfacing backend error details. `NotificationContext` (`src/context/`) polls once and feeds both the sidebar and mobile bell so they stay in sync — don't add a second poller. Pages are flat, one file per entity (list + kanban where relevant) plus `*Detail.jsx` for entity detail views; there's no shared CRUD abstraction across pages, so follow the pattern of the most similar existing page (e.g. `Contacts.jsx`/`ContactDetail.jsx`) rather than inventing a new structure.

**i18n**: all user-facing strings go through `i18next` (`src/i18n.js` holds the full EN/HU dictionaries inline — no external locale files). Add new keys to both language blocks together.

## CRM v2 migration (in progress — `INTEGRATION_PLAN.md` is the source of truth)

The repo is mid-migration from the MVP described above to an expanded CRM (access control, lead ownership/ball-in-court, milestone billing, deal→project automation, a scheduler, and an MCP server). **`INTEGRATION_PLAN.md`** (Hungarian) is the authoritative, phase-by-phase spec — read it in full before touching any phase's code; `DISCOVERY_REPORT.md` documents the pre-migration baseline it was written against. `INSTRUCTION.md` defines the working process (one feature-branch per phase, STOP-and-approve after each phase). This section is updated as each phase lands — treat it as the current-state summary, `INTEGRATION_PLAN.md` as the detailed design.

### New data model elements (introduced phase-by-phase, not all present yet)

- **`EventLog`** — generic, append-only audit trail: `entity_type`+`entity_id` (no DB FK — spans multiple tables), `event_type` (`created, deleted, updated, claimed, stage_changed, status_changed, role_changed, activity_logged, owner_changed, visibility_changed`, …; `deleted` was added in Phase 1, wired into every Company/Contact/Deal/Project/Activity delete handler — a genuine Phase 0 gap caught during Phase 1's own review), `from_value`/`to_value`, `actor_type`(`user`/`service`)+`actor_id`, optional `activity_id` FK, `note`, `created_at`. Written via a shared `log_event()` helper in `backend/utils.py` from every entity's write paths — `companies/contacts/deals/projects/activities` CRUD, `users` create/update/delete, `auth_router` register, and project time entries all log; `AppSetting`/notifications intentionally don't, since they aren't domain entities in this model. `won`/`lost` are not separate event types; they're a `stage_changed` with `to_value="won"/"lost"`. Rows are never deleted, even if the parent entity is hard-deleted. The raw `GET /api/event-logs?entity_type=&entity_id=` read endpoint (admin/manager only, `backend/routers/event_logs.py`) does **not** currently check whether the parent entity still exists — it returns whatever rows match, including for a deleted or never-existent id. A 404/"archived" response for that case is UI-facing `/timeline` behavior, not yet built (a later phase, per D9); don't assume it exists until it's actually implemented. A minimal read endpoint exists from Phase 0 so the log is observable/testable before any phase builds a real timeline view on top of it.
- **`EntityMembership`** — generic tagging table for the visibility model: `entity_type`, `entity_id`, `user_id`, `added_by`, `added_at`. The owner is auto-tagged. Grants access to `private` Deals/Projects beyond the owner.
- **`Milestone`** — belongs to a `Project` (CASCADE), replaces ad-hoc hourly billing for client-facing invoicing: `project_id`, `name`, `order_index`, `due_date`, `amount` XOR `percentage` (exactly one, enforced), separate `work_status` (`in_progress → client_review → accepted`) and `payment_status` (`not_due → invoiceable → invoiced → paid`) — independently settable, reversible in both directions, every change logged via `log_event`.
- **`ServiceAccount`** — API-key principal for machine/agent access (Phase 1, implemented; Phase 6 adds the actual MCP server plus an admin UI for managing these). `id`, `name`, `key_hash` (SHA-256 of the key, unique+indexed — the key is a high-entropy random token, not a user-chosen password, so fast exact-match lookup is the right property, not bcrypt's slow-hash brute-force resistance), `role` (same `admin/manager/user/guest` values as `User.role` — a service account is plugged into the *exact* same role+capability model, not a separate one), `active`, `created_by` (FK `users.id`, SET NULL), `created_at`. `backend/routers/service_accounts.py` (admin-only): `POST` creates and returns the raw key **once** (never retrievable again, only the hash is stored); `GET` lists (never exposes the key/hash); `PATCH` toggles `role`/`active` (prefer this over delete for revocation, so `EventLog.actor_id` stays attributable); `DELETE` hard-deletes. `frontend/src/pages/Settings.jsx` (Phase 6) has a "Service accounts" card exercising this: create shows the raw key once with a copy warning, list shows active/revoked, a checkbox toggles active, delete hard-deletes. Auth: `get_current_user()` (`auth.py`) checks the `X-API-Key` header first — if present, resolves to a `ServiceAccount` via `hash_api_key()` + exact match, otherwise falls through to the existing cookie/bearer JWT flow unchanged. Every one of the ~40 existing `Depends(get_current_user)` call sites across the routers works with either principal type automatically, with zero changes to those routers: `require_role`/`require_write`/`require_capability`/`log_event` (auto-infers `actor_type="service"` vs `"user"`) only ever read `.id`/`.role`/`.active` off whatever `get_current_user()` returned, and only `auth_router.py`/`users.py` touch `User`-only fields (`.email`/`.locale`) — verified by grep before relying on this, not assumed. **Known limitation, not yet solved**: `owner_id` (Company/Contact/Deal/Project/Activity) and `EntityMembership.user_id` are both hard FKs to `users.id` specifically — a service-authenticated create can't be "owned" or membership-tagged the same way a human's can (this surfaced as an actual `ForeignKeyViolation` during Phase 1's own testing). `utils.py::owner_id_for(actor)` returns `None` instead of erroring when `actor` is a `ServiceAccount`, so such writes land unassigned/ownerless rather than crashing — extending real per-service-account ownership/membership would need a schema change, deferred.
- **New fields**: `Deal.visibility` (`public`/`private`, Phase 1); `Deal.source` (`Literal["inbound","outreach","referral","other"]`, D10), `claimed_at`, `last_contact_at`, `ball_in_court` (`us`/`them`/`none`) — all Phase 2, implemented; `Deal.lead_type` (`single`/`double`), `contract_company_id`/`contract_contact_id` (FK, SET NULL — the paying/contracting party when it differs from the day-to-day contact), `referred_by_contact_id` (self-referential FK to `Contact`) — Phase 3, implemented; `Deal.is_stale` — Phase 5, implemented (job-maintained, see `backend/scheduler.py`, never written from a request path); `Activity.direction` (`inbound`/`outbound`/`internal`, Phase 0, implemented, replaces the old `[Inbound]/[Outbound]` subject-line prefix hack); `Project.deal_id` (FK, SET NULL, populated by the won→project automation) — Phase 4, implemented; `Project.closed_at`, `follow_up_days` (default 60), `satisfaction_score` — Phase 5, implemented.
- **`Milestone` templates + deal→project automation** (Phase 4, implemented) — `backend/milestone_templates.py` (`single_final`/`deposit_final`/`milestones` starter sets, `seed_project_milestones()` shared by both project-creation paths below) and `backend/deal_rules.py::create_project_from_won_deal` (idempotent via `Project.deal_id`, copies company/contact — or the `contract_*` party for a double-sided lead — value→budget, currency, owner, membership, and starter milestones).
- **Daily housekeeping scheduler** (Phase 5, implemented) — `backend/scheduler.py`: APScheduler cron (02:00) plus an admin manual-trigger (`POST /api/settings/housekeeping/run`, same function either way). Follow-up task creation (`Project.closed_at + follow_up_days` elapsed → an `Activity` for the owner, idempotent via an `EventLog` marker), `is_stale` maintenance, and re-running Phase 2's lazy notification checks for every active user. The advisory lock guarding cross-worker duplication (`entrypoint.sh` runs `--workers 2`) is acquired/released on a dedicated `engine.connect()` connection, deliberately not a pooled `Session` — a `Session.commit()` returns its connection to the pool, so a session-based lock can silently end up unlocked from a different physical connection than the one that locked it (verified empirically before fixing).
- Full field-level detail for each of these lives in `INTEGRATION_PLAN.md`, not duplicated here.

### Phase 2 — Lead ownership, ball-in-court, lifecycle (implemented)

- **Claim / unassigned (D1)**: `DealCreate.unassigned` (bool, default `False`, create-time-only — not a `Deal` column) is the one lever a client has over `owner_id`: `False` keeps the existing owner-is-creator behavior, `True` leaves `owner_id=None` so the deal sits in the shared inbox. `PATCH /api/deals/{id}/claim` lets any `manage_deals`-capable user take ownership of an unowned deal (400 if already owned); `PATCH /api/deals/{id}/owner` explicitly reassigns an already-owned deal and is the first route to actually enforce `reassign_owner` (Phase 1 modeled the capability but nothing checked it until now). Both log to `EventLog` (`claimed` / `owner_changed`) and auto-tag the (new) owner as an `EntityMembership`.
- **Owner-required stage guard (D1/BL-4)**: `deals.py::OWNER_REQUIRED_STAGES = {"proposal","negotiation","won","lost"}` — `PATCH /stage` and `PUT` both reject (`400`) moving into one of these while `owner_id IS NULL`. A lead can sit unclaimed at `lead`/`qualified` but can't progress further until claimed.
- **Ball-in-court (2.2)**: logging a directed `Activity` (`direction` inbound/outbound) against a `deal_id` auto-updates that deal's `ball_in_court` (`inbound→us`, `outbound→them`) and `last_contact_at` (`routers/deals.py::apply_ball_in_court_for_activity`, called from `activities.py::create_activity`); `internal`/no-direction activities don't touch it. `PATCH /api/deals/{id}/ball-in-court` allows a manual override. Every actual change logs a `ball_in_court_changed` event — this is the D4 pass-count metric's data source (a "pass" = one of these direction changes).
- **`backend/thresholds.py`** — D7's three business-day thresholds (`unassigned_days=2`, `awaiting_response_days=5`, `stale_days=14`), `AppSetting`-backed with the same stored-JSON-over-coded-defaults pattern as `capabilities.py`, admin-configurable via `GET/PUT /api/settings/thresholds`. `business_days_since()` is a plain Mon–Fri weekday count, no holiday calendar. `stale_days` is consumed by Phase 5's daily `is_stale` job (`backend/scheduler.py`).
- **Lazy reminders** (`notifications.py`, same `owner_id==user.id`-keyed pattern as overdue tasks/at-risk projects): `auto_unclaimed_lead` surfaces to whoever has `view_all_reports` (managers/admin) once an unowned deal has sat past `unassigned_days` — routed there, not to a specific assignee, since an unowned deal isn't anyone's by definition (JV-10). `auto_awaiting_response` surfaces to the deal's own owner once `ball_in_court='us'` has sat past `awaiting_response_days`. Both are computed on every `GET /api/notifications` call, not a background job — Phase 5's daily job is meant to make this reliable independent of who opens the app.
- **Lifecycle timeline + analytics**: `GET /api/deals/{id}/timeline` returns the deal's `EventLog` rows chronologically, each `activity_logged` entry enriched with the linked `Activity`'s `direction`/`subject`. `GET /api/reports/deal-flow` (`view_all_reports`) returns won/lost counts+ratio, average pass-count-to-won, and average days per stage (reconstructed from each deal's `stage_changed` history — the first transition's `from_value` is the stage it was created in). Neither endpoint is visibility-scoped for the report (matches `reports/utilization`'s existing precedent that `view_all_reports` implies org-wide data); the timeline endpoint is `can_see`-gated per deal like every other deal detail route.

### Phase 6 — MCP server (implemented)

- **`mcp-server/`** — a separate deployable service (own `Dockerfile`, own `docker-compose.yml` entry, only starts if `CRM_MCP_API_KEY` is set) exposing 11 tools to an external AI agent over MCP (`mcp` Python SDK, `streamable-http` transport). `crm_client.py` is a thin `httpx` wrapper that calls the CRM's own REST API with `X-API-Key` auth — **never the database directly** — so every capability check, visibility rule, and financial-masking dependency the tools are subject to is identical to what a human user with the service account's role would get. Read tools: `list_deals`, `list_projects`, `get_deal_detail`, `get_project_detail`, `get_deal_timeline`, `get_deal_flow_report`. Write tools: `create_lead`, `claim_deal`, `change_deal_stage`, `log_activity`, `set_milestone_status`. Deliberately excludes delete/owner-reassignment/visibility-change tools (least-privilege first tool set, per the plan). `claim_deal` is included even though the backend always rejects it for a service-account principal (`deals.py::claim_deal`'s existing `isinstance(user, User)` check) — kept so the agent/operator sees the backend's own rejection reason rather than the tool being silently hidden; the backend decision is the single source of truth, not the MCP layer.
- **Rate limiting keyed by API key (audit A-7)**: `rate_limit.py::get_client_ip` now checks `X-API-Key` first and keys on its SHA-256 hash (matching how the key itself is stored) — every MCP call would otherwise come from the same container IP, landing every service account sharing that container in one shared bucket. Falls through to the existing IP-based key (`X-Real-IP` behind nginx, else the raw peer address) when no API key is present, so cookie/bearer-JWT-authenticated requests are unaffected.
- **Service Accounts admin UI** (`frontend/src/pages/Settings.jsx`): the API existed since Phase 1 but had no UI until a real consumer (the MCP server) existed. Create shows the raw key once with a "copy now" warning (never retrievable again, matching the API's own contract); list shows name/role/active; a checkbox toggles `active` (revocation without losing `EventLog` attribution); delete hard-deletes.

### Access model (4 layers, replacing plain `ROLE_LEVELS` gating)

1. **Role** (unchanged) — `admin/manager/user/guest`, `ROLE_LEVELS` hierarchy in `auth.py`. Admin and manager always see everything.
2. **Object visibility** — `Deal`/`Project.visibility` (`public`/`private`), org-wide default `public` (admin-configurable).
3. **Membership** — `EntityMembership`; owner auto-tagged; only members (+ admin/manager) see a `private` object.
4. **Capability matrix** — a bounded, admin-configurable set of 7 capabilities (`view_financials`, `manage_deals`, `manage_projects`, `invite_members`, `set_visibility`, `reassign_owner`, `view_all_reports`), stored as JSON under an `AppSetting` key (`role_capabilities`, `backend/capabilities.py`), enforced via `require_capability()` (`auth.py`, same shape as `require_role`/`require_write`). `manage_users`/`configure_permissions` are fixed to admin-only via `require_role("admin")`, never in the matrix, never configurable.

**Authz precedence (Phase 1, implemented — not just planned)**: for the routes a capability actually covers, `require_capability` fully *replaces* `require_role`/`require_write` — never stacked together on the same route. Concretely: `deals.py`/`projects.py` entity create/update/delete use `manage_deals`/`manage_projects`; their `PATCH .../visibility` uses `set_visibility`; their `.../members` endpoints use `invite_members`; `reports.py`'s utilization report uses `view_all_reports`. Everywhere a capability doesn't apply — `companies.py`/`contacts.py`/`activities.py` CRUD, `projects.py`'s time-entry sub-resource endpoints, `data_io.py`'s CSV import — the original `require_write` is untouched (the plan's capability table only names `manage_deals`/`manage_projects` as entity-write capabilities, so Contact/Company/Activity/TimeEntry writes staying role-based is a deliberate scope boundary, not an oversight). `users.py`/`settings_router.py` stay on `require_role("admin")` since they gate the two fixed, non-configurable capabilities. **The capability check applies regardless of which surface triggers the write**: `ai_router.py`'s `create_deal`/`create_project` actions check `manage_deals`/`manage_projects` via `has_capability()` directly (not through a route dependency, since one endpoint handles 5 action types) — catching a real gap where the AI command bar could bypass an admin revoking those capabilities. The AI flow's create paths also now set `visibility` from the org default and auto-add the creator as a member, mirroring the direct API — without that, an AI-created deal later set to `private` would lock its own creator out (visibility is EntityMembership-based, not an `owner_id` check).

Visibility filtering and financial masking (see below) are applied everywhere Deal/Project data can leak: `deals.py`/`projects.py` (list+detail+get, plus write endpoints via `can_see()` so a capability alone can't reach an invisible private record), `companies/{id}/detail`, `contacts/{id}/detail`, `dashboard.py`, and the `data_io.py` CSV export (which had no role-gate at all before Phase 1 — `require_write` was added there specifically).

### Conventions introduced by the migration (apply from the phase that lands them onward)

- **Every enum-like field gets a Pydantic `Literal`** in `schemas.py` — no more router-local `VALID_*` set checks as the only validation (this closes the pre-existing `Project.priority`/`User.role` gap).
- **Every write path logs via `log_event()`** (`backend/utils.py`) — don't hand-roll ad-hoc audit inserts.
- **Financial masking is one shared serializer-dependency**, not per-field conditionals scattered across routers: money fields (`Deal.value`, `Project.budget`/`hourly_rate`, `Milestone.amount`) become `Optional` in the `*Out` schemas, and a common dependency nulls them out when the caller lacks `view_financials`. Non-`*Out`-based surfaces (`dashboard.py` KPIs, CSV export) need the masking applied explicitly since they bypass the schema layer.
- **Schema migrations are Alembic-only from Phase 0 onward** — `Base.metadata.create_all` and the ad-hoc `ALTER TABLE IF NOT EXISTS` lines in `server.py:56-59` are retired; `alembic upgrade head` runs before `seed()`, both in the Docker entrypoint and in the pytest fixtures (which hit a live server, so the DB must be migrated before tests start).
- **`owner_id`/`user_id` ownership fields stay server-set, never client input** — the existing pattern (`owner_id=user.id` at creation, excluded from all Create/Update schemas) extends to the new `unassigned`-flag-based claim flow; still no endpoint accepts an arbitrary `owner_id`.

### Working method for this migration

- One feature branch per phase (e.g. `feat/phase-0-foundations`); never commit migration work directly to `main`.
- **Definition of done = all tests green.** New functionality needs a new pytest integration test (against a live seeded server, per the existing `backend/tests/` pattern); if a phase's change legitimately alters an existing test's expected behavior (e.g. invalid enums now 422 instead of silently falling back), update that test as part of the same phase.
- One commit per logical feature within a phase, not one giant phase-commit.
- **Stop after every phase and Step 0**, report what changed and the test results, and wait for explicit approval before starting the next phase — don't jump ahead.
- If the plan is ambiguous or self-contradictory for the code as it stands, stop and ask rather than guessing.
- **End-of-phase audit, before the phase counts as done.** Green tests are necessary but not sufficient. Before reporting a phase complete (and again before merging it to `main`), audit it across five dimensions and fix everything the audit finds:
  1. **Completeness** — every requirement in that phase's `INTEGRATION_PLAN.md` section is actually implemented, backend *and* frontend (a backend-only feature with no UI to use it is a gap, not a deferred nice-to-have, unless the plan explicitly says so).
  2. **Architecture** — is the new code's placement consistent with the codebase's established patterns (one small module per cross-cutting concern, router file per entity, etc.), and free of duplicated logic that should share a helper.
  3. **Security** — IDOR/visibility bypass on every new endpoint, authz-precedence consistency, ServiceAccount principal safety (a FK column that only expects a `User` row is the recurring bug class here), input validation, data exposure (financial masking, capability gating).
  4. **Test coverage** — does the new test file actually exercise every branch the audit's other dimensions surfaced (permission-denied paths, private-object 404s on *every* new mutating endpoint, edge cases in any non-trivial date/state-machine logic), not just the happy path.
  5. **Frontend/UX** — is the new UI actually usable, not just present: do new features have a real entry point a human can find (not API/AI-only), does error handling show a real diagnostic (not a swallowed generic message), is the visual integration consistent with the rest of the app.
  **Run the five dimensions as parallel subagents, not sequentially** — one agent per dimension, launched together: this keeps each review unbiased by the others' findings *and* keeps the whole audit fast (five reviews in the time of one, not five times as long). Then spot-check the most severe claims directly against the code before acting on them — an audit finding is a claim to verify, not a fact to trust blindly.
- **Audit-fix commits land on a branch, not directly on `main`**, same as the phase itself — including a fix round run *after* the phase's branch was already merged (e.g. a follow-up audit on `main`): branch off, commit the fixes there, verify, then merge that branch back into `main`. Direct-to-`main` commits are reserved for genuinely urgent, narrowly-scoped production hotfixes (e.g. a broken deploy), not routine audit remediation.

### Locked decisions (D1–D11 — not open questions, implement to these values)

| # | Decision | Locked value |
|---|---|---|
| D1 | Owner requirement | An unassigned lead may sit in the shared inbox, but can't advance past `qualified`, and project creation requires an owner. |
| D2 | Financial masking | Pattern "A" — `Optional` fields in `*Out` schemas + one shared nulling serializer-dependency. |
| D3 | Time tracking's role | Internal cost/utilization only; client billing runs off milestones, not the hourly rate. |
| D4 | "Pass" metric | Number of `ball_in_court` direction changes. |
| D5 | Visibility default | New Deal/Project defaults to `public` (admin can change the global default). |
| D6 | `view_financials` default | admin ✅, manager ✅, user ✅ (on), guest ❌ (off). |
| D7 | Thresholds (business days, global, admin-configurable) | unassigned: **2** · awaiting-response: **5** · stale: **14**. |
| D8 | Ball-in-court threading | One thread per deal for now (no per-topic sub-threads). |
| D9 | EventLog timeline UI rollout order | Deal first, then Project (logging itself covers every `entity_type` from Phase 0). |
| D10 | `Deal.source` enum | `inbound` / `outreach` / `referral` / `other`. |
| D11 | Milestone amount | `amount` XOR `percentage` — exactly one must be set. |

Accepted simplification: visibility/membership applies only to Deal and Project — Contacts and Companies stay visible to every logged-in user (client PII, referral graph). Google Workspace integration (SSO, Gmail/Calendar auto-logging) is explicitly out of scope; the `google_*` User columns stay dead fields.

## Security-sensitive defaults (do not regress)

These were deliberately hardened in a past audit — see the README's Security Audit section for the reasoning:
- `ALLOW_REGISTRATION=false` by default — self-registration must stay opt-in.
- `RATE_LIMITING_ENABLED=true` by default (`backend/rate_limit.py`, slowapi) — only disable via env for test runs, never in code.
- `COOKIE_SECURE` must stay env-driven, not hardcoded — `false` breaks nothing locally but `true` is required whenever cookies cross HTTPS.
- Any new entity enum field should get a Pydantic `Literal` type in `schemas.py`, matching the existing pattern, rather than an unconstrained `str`.

## PR / commit expectations

No CI pipeline or PR template exists in this repo. Before handing off backend changes, run the pytest suite against a running, seeded backend (see Tests above). There's no enforced commit message convention — recent history uses short, plain descriptions of the change.
