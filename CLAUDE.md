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
Tests log in as the seeded demo accounts (`admin@wespeak.ai` / `admin123`, etc. — see `backend/tests/conftest.py`), so a fresh/seeded DB is required.

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

**Startup seeding** (`server.py::seed()`): runs on every app startup. Creates tables via `Base.metadata.create_all`, applies a couple of ad-hoc `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` migrations inline (there is no Alembic — schema changes to existing columns need a new idempotent `ALTER` statement added here), and seeds the admin account + 3 demo users + sample CRM data **only if they don't already exist** (admin password is not reset on restart).

**Frontend**: CRA (JS/JSX, not TS). `App.js` defines all routes wrapped in a `Protected` component that checks `useAuth()` and an optional `roles`/`adminOnly` prop — this is the only route-level RBAC; page components assume they're already authorized. `api.js` is a single shared axios instance (`withCredentials: true`, baseURL from `REACT_APP_BACKEND_URL`) — always import it rather than creating new axios instances, and use its `formatApiError()` for surfacing backend error details. `NotificationContext` (`src/context/`) polls once and feeds both the sidebar and mobile bell so they stay in sync — don't add a second poller. Pages are flat, one file per entity (list + kanban where relevant) plus `*Detail.jsx` for entity detail views; there's no shared CRUD abstraction across pages, so follow the pattern of the most similar existing page (e.g. `Contacts.jsx`/`ContactDetail.jsx`) rather than inventing a new structure.

**i18n**: all user-facing strings go through `i18next` (`src/i18n.js` holds the full EN/HU dictionaries inline — no external locale files). Add new keys to both language blocks together.

## Security-sensitive defaults (do not regress)

These were deliberately hardened in a past audit — see the README's Security Audit section for the reasoning:
- `ALLOW_REGISTRATION=false` by default — self-registration must stay opt-in.
- `RATE_LIMITING_ENABLED=true` by default (`backend/rate_limit.py`, slowapi) — only disable via env for test runs, never in code.
- `COOKIE_SECURE` must stay env-driven, not hardcoded — `false` breaks nothing locally but `true` is required whenever cookies cross HTTPS.
- Any new entity enum field should get a Pydantic `Literal` type in `schemas.py`, matching the existing pattern, rather than an unconstrained `str`.
