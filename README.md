# wespeak.ai CRM

Self-hosted, mobile-first CRM for [wespeak.ai](https://wespeak.ai) — an AI consulting company.
Built for a small team (5–10 users), runs on a single Hetzner box, bilingual (English/Hungarian),
with an AI command bar powered by OpenRouter.

## Project Goals

- **Self-hosted & lightweight**: one server, Docker Compose, no SaaS dependencies.
- **Mobile-first**: bottom-nav on phones, sidebar on desktop, responsive throughout.
- **AI-native**: free-form text commands create contacts, deals, projects, and more.
- **Role-based**: admin / manager / user / guest with enforced permissions (backend + frontend).
- **Bilingual**: full EN/HU translation via i18next, language stored per-user.

## Scope

### Core CRM (Iteration 1)
- **Contacts & Companies**: CRUD with owner assignment, status tracking (lead → prospect → customer), tags, company linking.
- **Deals**: kanban pipeline (lead / qualified / proposal / negotiation / won / lost) with drag-and-drop, value, probability, expected close date. List view also available.
- **Projects**: status (planning / active / on_hold / completed / cancelled), priority, budget, estimated hours, hourly rate, company/contact links.
- **Activities**: tasks, calls, emails, meetings, notes — with due dates, completion tracking, and linking to contacts/companies/deals/projects.
- **Dashboard**: KPI tiles (total deals, pipeline value, contacts, overdue tasks) + charts (pipeline by stage, contacts by status, upcoming tasks).
- **Auth**: JWT in httpOnly cookies, bcrypt password hashing, 4 roles with enforced RBAC.

### Detail Pages & Time Tracking (Iteration 2)
- **Entity detail pages**: Contact, Company, Deal, Project — with related records and activity timelines.
- **Time tracking**: per-project TimeEntry (hours, billable flag, billable amount via project hourly_rate).
- **Project health**: on_track / at_risk / over_budget / completed / cancelled based on logged vs estimated hours and deadlines.
- **Calendar**: month view of activities, click-to-navigate.
- **CSV import/export**: contacts, companies, deals, projects. Import auto-creates companies for unknown names.

### Utilization, Notifications & Email Logging (Iteration 3)
- **Utilization report**: per-user billable hours, amounts, and utilization % by week/month. Admin + manager only. Bar chart + table.
- **In-app notifications**: auto-generated for overdue tasks, tasks due today, and at-risk projects. Bell icon with unread badge, mark-read/mark-all. Shared React context (single poll, multiple bells in sync).
- **Email logging**: record inbound/outbound emails as activities on the contact timeline.

### Backlog
- Google Workspace OAuth (login + Gmail + Calendar sync) — scaffold ready, needs OAuth credentials.
- Two-way Gmail sync once Workspace connected.

## System Architecture

```
┌─────────────────────────────────────────────────┐
│                   Browser (SPA)                  │
│  React 18 + Tailwind + i18next + recharts        │
│  Port 3000 (nginx serves static build +          │
│  proxies /api → backend:8001)                     │
└──────────────────────┬──────────────────────────┘
                       │ HTTPS (cookies: httpOnly, Secure, SameSite=None)
                       ▼
┌─────────────────────────────────────────────────┐
│              Backend (FastAPI)                    │
│  Port 8001 (localhost only)                      │
│                                                  │
│  Routers:                                        │
│    /api/auth       — login, register, me, logout │
│    /api/users      — user CRUD (admin)           │
│    /api/contacts   — CRUD + CSV                  │
│    /api/companies  — CRUD + CSV                  │
│    /api/deals      — CRUD + stage update         │
│    /api/projects   — CRUD + time entries + health│
│    /api/activities — CRUD + calendar             │
│    /api/dashboard  — KPIs + charts               │
│    /api/reports    — utilization (manager+)      │
│    /api/notifications — auto + manual, sync      │
│    /api/ai         — command → OpenRouter        │
│    /api/settings    — OpenRouter key/model       │
│    /api/data-io     — CSV import/export          │
└──────┬──────────────┬───────────────────────────┘
       │              │
       ▼              ▼
┌────────────┐  ┌──────────────────┐
│ PostgreSQL │  │  OpenRouter API   │
│  Port 5432 │  │  (chat completion)│
│  (localhost│  │  Key encrypted    │
│   only)    │  │  with Fernet      │
└────────────┘  └──────────────────┘
```

### Backend

| File | Responsibility |
|---|---|
| `backend/server.py` | FastAPI app, CORS, router registration, startup seed (admin user + demo data) |
| `backend/database.py` | SQLAlchemy engine/session factory (`DATABASE_URL` from env), `get_db` dependency |
| `backend/models.py` | 10 SQLAlchemy models: User, Company, Contact, Deal, Project, Activity, TimeEntry, Notification, AppSetting, AICommandLog |
| `backend/auth.py` | bcrypt hashing, JWT create/verify (HS256), httpOnly cookie helpers, `get_current_user`, `require_role`, `require_write` (guests read-only) |
| `backend/schemas.py` | Pydantic v2 request/response models for all entities |
| `backend/ai_service.py` | OpenRouter chat completions, Fernet encrypt/decrypt for API keys, system prompt for structured JSON responses |
| `backend/routers/` | 12 API routers (auth, users, contacts, companies, deals, projects, activities, dashboard, reports, notifications, ai, settings, data_io) |

**Auth flow**: email/password → bcrypt verify → JWT access (12h) + refresh (7d) in httpOnly cookies. Token extracted from cookie or `Authorization: Bearer` header. Role levels: guest=0, user=1, manager=2, admin=3.

**AI flow**: user types free-form command → backend sends system prompt + command to OpenRouter → LLM returns structured JSON `{action, data, message}` → backend executes the action (create_contact, create_deal, etc.) or returns the answer.

### Frontend

| Area | Details |
|---|---|
| `frontend/src/App.js` | Route definitions, `Protected` wrapper (auth + role checks) |
| `frontend/src/auth.jsx` | AuthProvider context, login/register/logout, `useAuth` hook |
| `frontend/src/api.js` | Axios instance (`/api` base, `withCredentials`), `formatApiError` helper |
| `frontend/src/i18n.js` | i18next setup, EN/HU translation dictionaries |
| `frontend/src/pages/` | 15 page components (Dashboard, Contacts, Companies, Deals, Projects, Activities, Calendar, Utilization, Users, Settings, Login + 5 detail pages) |
| `frontend/src/components/` | Layout (responsive nav), common UI (Spinner, Modal, etc.), AICommandBar, NotificationBell |
| `frontend/src/context/` | NotificationContext (shared notification state) |

### Infrastructure

| Component | Details |
|---|---|
| `docker-compose.yml` | 3 services: `db` (Postgres 15-alpine), `backend` (FastAPI/uvicorn :8001), `frontend` (nginx :3000 → proxies `/api`) |
| `scripts/backup.sh` | `pg_dump` with gzip, rotation |
| `scripts/restore.sh` | Restore from gzip backup |
| `frontend/nginx.conf` | SPA fallback + `/api` reverse proxy to backend |
| `.env` | `DATABASE_URL`, `JWT_SECRET`, `FERNET_KEY`, `FRONTEND_URL`, `ADMIN_EMAIL/PASSWORD`, `POSTGRES_*` |

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, FastAPI 0.110, SQLAlchemy 2.0, Pydantic v2, uvicorn |
| Database | PostgreSQL 15 (Alpine) |
| Auth | PyJWT (HS256), bcrypt, httpOnly Secure cookies |
| AI | OpenRouter chat completions API, Fernet encryption for key storage |
| Frontend | React 18 (CRA), Tailwind CSS 3, i18next, recharts, @hello-pangea/dnd, lucide-react icons, axios |
| Deployment | Docker Compose, nginx reverse proxy, Caddy/Let's Encrypt for TLS |

## Quick Start

### Prerequisites
- Docker + Docker Compose
- OpenSSL or Python (to generate `JWT_SECRET` and `FERNET_KEY`)

### Local Development
```bash
# Backend
cd backend
pip install -r requirements.txt
export DATABASE_URL="postgresql+psycopg2://crm_user:change_me@localhost:5432/wespeak_crm"
export JWT_SECRET="your-secret"
export FERNET_KEY="your-fernet-key"
uvicorn server:app --reload --port 8001

# Frontend (separate terminal)
cd frontend
npm install
REACT_APP_BACKEND_URL=http://localhost:8001 npm start
```

### Docker (Production)
```bash
cp .env.example .env
# Generate secrets:
python3 -c "import secrets; print('JWT_SECRET='+secrets.token_hex(48))"
python3 -c "from cryptography.fernet import Fernet; print('FERNET_KEY='+Fernet.generate_key().decode())"
# Edit .env with the generated values, then:
docker compose up -d --build
```

App available at `http://localhost:3000`. See [DEPLOYMENT.md](DEPLOYMENT.md) for the full Hetzner production guide.

## Default Accounts

Seeded on first start (change in production):

| Email | Password | Role |
|---|---|---|
| `admin@wespeak.ai` | `admin123` | admin |
| `manager@wespeak.ai` | `manager123` | manager |
| `user@wespeak.ai` | `user123` | user |
| `guest@wespeak.ai` | `guest123` | guest (read-only) |

## Testing

```bash
# Backend
cd backend && pytest -v
# 49 tests across 3 iteration suites
```

## Security Audit (Iteration 4)

Full security audit performed and all findings remediated:

### Authentication & Authorization
- **Registration disabled by default** — `ALLOW_REGISTRATION=false`. Admins create users via `/api/users`.
- **Rate limiting** on login (5/min), register (3/min), refresh (10/min) via `slowapi`. Disable for tests: `RATE_LIMITING_ENABLED=false`.
- **Cookie hardening** — `SameSite=Lax` (was `None`), `Secure` flag configurable via `COOKIE_SECURE` env (set `false` for local HTTP, `true` for production HTTPS).
- **Admin password no longer reset on restart** — seed only creates the account on first run.

### Data Integrity
- **FK cascade rules** — all optional foreign keys use `ON DELETE SET NULL`; `TimeEntry` and `Notification` use `ON DELETE CASCADE`.
- **Delete handlers** clean up child records before parent deletion (companies, contacts, deals).
- **AI entity validation** — LLM-generated data validated against allowed enum values before creating records.
- **CSV import dedup** — duplicate emails skipped with error; status field validated.

### Input Validation
- **Pydantic Literal types** on all enum fields: deal stage, contact status, project status, activity type.
- **Typed locale update** — `/api/users/me/locale` uses `LocaleUpdate` Pydantic model (was untyped `dict`).

### Code Quality
- **requirements.txt trimmed** from 129 to 16 packages (removed unused boto3, stripe, pandas, motor, etc.).
- **N+1 query fixed** in contacts list (`joinedload` on company).
- **Shared utilities** — `logged_hours_for()` extracted to `backend/utils.py`.
- **Inline imports** moved to module level across all routers.
- **CORS tightened** — explicit method/header lists instead of wildcards.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `COOKIE_SECURE` | `false` | Set `true` for HTTPS (production), `false` for HTTP (local) |
| `ALLOW_REGISTRATION` | `false` | Enable public self-registration |
| `RATE_LIMITING_ENABLED` | `true` | Disable for test suites (`RATE_LIMITING_ENABLED=false`) |

See `.env.example` for the full list with generation instructions.

## Project Structure

```
wsai-crm/
├── backend/
│   ├── server.py            # FastAPI app + seed
│   ├── database.py          # SQLAlchemy setup
│   ├── models.py            # 10 ORM models (with ondelete cascade)
│   ├── schemas.py           # Pydantic schemas (Literal enum validation)
│   ├── auth.py              # JWT + RBAC + configurable cookies
│   ├── ai_service.py        # OpenRouter + Fernet
│   ├── rate_limit.py        # slowapi limiter (configurable)
│   ├── utils.py             # Shared utilities (logged_hours_for)
│   ├── routers/             # 12 API routers
│   ├── tests/               # pytest (49 tests)
│   ├── Dockerfile
│   └── requirements.txt     # 16 pinned packages
├── frontend/
│   ├── src/
│   │   ├── App.js           # Routes + Protected wrapper
│   │   ├── auth.jsx         # Auth context
│   │   ├── api.js           # Axios instance
│   │   ├── i18n.js          # EN/HU translations
│   │   ├── pages/           # 15 page components
│   │   ├── components/      # Layout, AICommandBar, NotificationBell, common
│   │   └── context/         # NotificationContext
│   ├── Dockerfile           # npm build (not yarn)
│   └── nginx.conf
├── docker-compose.yml
├── .env.example             # Template with all env vars
├── scripts/                 # backup.sh, restore.sh
├── memory/                  # PRD, test credentials
├── test_reports/            # Iteration test results
└── DEPLOYMENT.md            # Hetzner production guide
```
