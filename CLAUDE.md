# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

wespeak.ai CRM — self-hosted, mobile-first CRM for a small (5–10 user) AI consulting company. FastAPI + PostgreSQL backend, React 18 (CRA) frontend, bilingual EN/HU (i18next), AI command bar via OpenRouter. Runs as 3 Docker Compose services (`db`, `backend`, `frontend`) behind nginx on a single Hetzner box. See [README.md](README.md) for full feature scope and [DEPLOYMENT.md](DEPLOYMENT.md) for the production runbook.

## Commands

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

### Tests
The pytest suites are **integration tests that hit a live server** over HTTP (`requests`, `BASE_URL` from `REACT_APP_BACKEND_URL`, default `http://localhost:8001`) — there is no FastAPI `TestClient` / in-memory DB. The backend must be running and seeded before running tests:
```bash
cd backend
export RATE_LIMITING_ENABLED=false   # avoid 429s from login-heavy test runs
pytest -v                            # all 49 tests (backend_test.py, test_iteration2.py, test_iteration3.py)
pytest tests/test_iteration3.py -v   # single suite
pytest tests/test_iteration3.py::TestNotifications -v   # single class
```
Tests log in as the seeded demo accounts (`admin@wespeak.ai` / `admin123`, etc. — see `backend/tests/conftest.py`), so a fresh/seeded DB is required. A session-scoped autouse fixture in `conftest.py` runs `alembic upgrade head` before any test (requires `DATABASE_URL` to be set in the test-running shell, pointing at the same DB the server under test uses).

There is no frontend test suite in active use (`npm test` runs CRA's default Jest runner but no test files exist beyond CRA's scaffold).

### Docker (full stack)
```bash
cp .env.example .env   # then fill in JWT_SECRET, FERNET_KEY, passwords
docker compose up -d --build
```

## Architecture

**Auth**: email/password → bcrypt → JWT (`backend/auth.py`), access (12h) + refresh (7d), both in httpOnly cookies (`SameSite=Lax`, `Secure` gated by `COOKIE_SECURE`). Token is read from the cookie or an `Authorization: Bearer` header (`_extract_token`). Roles are a strict hierarchy in `ROLE_LEVELS`: `guest=0 < user=1 < manager=2 < admin=3`. Two dependencies gate endpoints: `require_role(min_role)` for level checks and `require_write` for the guest-is-read-only rule — apply both, not one, when a route needs both a floor role and write protection.

**Router pattern** (`backend/routers/*.py`, one file per entity, all registered in `server.py`): each router does its own SQLAlchemy queries directly against `models.py` (no repository/service layer), converts ORM objects to Pydantic `*Out` schemas via a local `_to_out()` helper (denormalizes things like `company_name` onto the output), and depends on `get_current_user` (read) or `require_write` (mutate). Delete handlers must manually null out or cascade child FKs before deleting a parent — see `contacts.py::delete_contact` for the pattern; DB-level `ondelete` rules in `models.py` are `SET NULL` for most optional FKs and `CASCADE` only for `TimeEntry`/`Notification`.

**AI command flow** (`backend/ai_service.py` + `routers/ai_router.py`): user free-form text → OpenRouter chat completion with a fixed system prompt requesting strict JSON (`{action, data, message}`) → backend validates `data` fields against the same enums used elsewhere (deal stage, contact status, etc.) before creating a record. The OpenRouter API key is stored encrypted (Fernet, `FERNET_KEY` env) in `AppSetting`, settable per-instance via the Settings page, falling back to `OPENROUTER_API_KEY` env.

**Data model** (`backend/models.py`): 10 tables, string UUID PKs (`gen_id()`). Core entities — `Company`, `Contact`, `Deal`, `Project`, `Activity` — all carry an `owner_id` (nullable FK to `User`, `SET NULL` on delete) and most enum-like fields (`status`, `stage`, `type`, `priority`) are plain strings validated only at the Pydantic layer (`schemas.py` uses `Literal[...]`) — the DB itself does not enforce the enum. `TimeEntry` belongs to a `Project` (CASCADE) and feeds billing via `Project.hourly_rate`; `backend/utils.py::logged_hours_for()` is the shared aggregation used wherever "hours logged" needs to be computed — reuse it instead of re-summing `TimeEntry`.

**Schema migrations**: Alembic-owned (`backend/alembic/`, config in `backend/alembic.ini` + `backend/alembic/env.py`). `env.py` reads `DATABASE_URL` from the environment (same var `database.py` uses) and targets `Base.metadata` from `models.py` — one env var drives both the app and its migrations. There is a single baseline revision covering the schema as of the CRM v2 migration's start; new schema changes get their own revision (`alembic revision --autogenerate -m "..."`) rather than hand-edited `ALTER TABLE` statements.

**Bootstrap sequence** (migrate → seed → serve): `alembic upgrade head` then `seed()` (`server.py`) run once, in that order, **before** uvicorn starts — in Docker via `backend/entrypoint.sh`, for local dev as two explicit commands (see Commands above), and in the test suite the migration step runs via an autouse session fixture in `backend/tests/conftest.py`. Neither step is a FastAPI startup hook: with `--workers 2`, a startup-event hook would run once per worker process and race itself (this is exactly what happened when `seed()` used to be wired to `@app.on_event("startup")` — two workers double-inserted the admin user). `seed()` itself seeds the admin account + 3 demo users + sample CRM data **only if they don't already exist** (admin password is not reset on restart) and is safe to call from a script (`python -c "from server import seed; seed()"`) since it does its own session-scoped DB work, not app startup.

**Frontend**: CRA (JS/JSX, not TS). `App.js` defines all routes wrapped in a `Protected` component that checks `useAuth()` and an optional `roles`/`adminOnly` prop — this is the only route-level RBAC; page components assume they're already authorized. `api.js` is a single shared axios instance (`withCredentials: true`, baseURL from `REACT_APP_BACKEND_URL`) — always import it rather than creating new axios instances, and use its `formatApiError()` for surfacing backend error details. `NotificationContext` (`src/context/`) polls once and feeds both the sidebar and mobile bell so they stay in sync — don't add a second poller. Pages are flat, one file per entity (list + kanban where relevant) plus `*Detail.jsx` for entity detail views; there's no shared CRUD abstraction across pages, so follow the pattern of the most similar existing page (e.g. `Contacts.jsx`/`ContactDetail.jsx`) rather than inventing a new structure.

**i18n**: all user-facing strings go through `i18next` (`src/i18n.js` holds the full EN/HU dictionaries inline — no external locale files). Add new keys to both language blocks together.

## CRM v2 migration (in progress — `INTEGRATION_PLAN.md` is the source of truth)

The repo is mid-migration from the MVP described above to an expanded CRM (access control, lead ownership/ball-in-court, milestone billing, deal→project automation, a scheduler, and an MCP server). **`INTEGRATION_PLAN.md`** (Hungarian) is the authoritative, phase-by-phase spec — read it in full before touching any phase's code; `DISCOVERY_REPORT.md` documents the pre-migration baseline it was written against. `INSTRUCTION.md` defines the working process (one feature-branch per phase, STOP-and-approve after each phase). This section is updated as each phase lands — treat it as the current-state summary, `INTEGRATION_PLAN.md` as the detailed design.

### New data model elements (introduced phase-by-phase, not all present yet)

- **`EventLog`** — generic, append-only audit trail: `entity_type`+`entity_id` (no DB FK — spans multiple tables), `event_type` (`created, deleted, claimed, stage_changed, status_changed, activity_logged, owner_changed, visibility_changed`, …; `deleted` was added in Phase 1, wired into every Company/Contact/Deal/Project/Activity delete handler — a genuine Phase 0 gap caught during Phase 1's own review), `from_value`/`to_value`, `actor_type`(`user`/`service`)+`actor_id`, optional `activity_id` FK, `note`, `created_at`. Written via a shared `log_event()` helper in `backend/utils.py` from **every** write path, for **every** `entity_type`, starting at Phase 0 — even before an entity has a timeline UI. `won`/`lost` are not separate event types; they're a `stage_changed` with `to_value="won"/"lost"`. Rows are never deleted, even if the parent entity is hard-deleted (deleted entities' `/timeline` returns 404/"archived", not a dangling error). A minimal read endpoint (`GET /api/event-logs?entity_type=&entity_id=`, admin/manager only, `backend/routers/event_logs.py`) exists from Phase 0 too — a raw chronological dump, not the eventual UI-facing `/timeline`, added so the log is observable/testable before any phase builds a real timeline view on top of it.
- **`EntityMembership`** — generic tagging table for the visibility model: `entity_type`, `entity_id`, `user_id`, `added_by`, `added_at`. The owner is auto-tagged. Grants access to `private` Deals/Projects beyond the owner.
- **`Milestone`** — belongs to a `Project` (CASCADE), replaces ad-hoc hourly billing for client-facing invoicing: `project_id`, `name`, `order_index`, `due_date`, `amount` XOR `percentage` (exactly one, enforced), separate `work_status` (`in_progress → client_review → accepted`) and `payment_status` (`not_due → invoiceable → invoiced → paid`) — independently settable, reversible in both directions, every change logged via `log_event`.
- **`ServiceAccount`** — API-key principal for machine/agent access (MCP server enabler), plugged into the same capability model as human users; auth via `X-API-Key` alongside the existing cookie/bearer JWT flow in `auth.py`.
- **New fields**: `Deal.visibility` (`public`/`private`), `lead_type` (`single`/`double`), `contract_company_id`/`contract_contact_id` (FK, SET NULL — the paying/contracting party when it differs from the day-to-day contact), `referred_by_contact_id` (self-referential FK to `Contact`), `source` (`Literal["inbound","outreach","referral","other"]`), `ball_in_court` (`us`/`them`/`none`), `last_contact_at`, `claimed_at`, `is_stale`; `Activity.direction` (`inbound`/`outbound`/`internal`, replaces the old `[Inbound]/[Outbound]` subject-line prefix hack); `Project.deal_id` (FK, SET NULL, populated by the won→project automation), `closed_at`, `follow_up_days` (default 60), `satisfaction_score`.
- Full field-level detail for each of these lives in `INTEGRATION_PLAN.md`, not duplicated here.

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
