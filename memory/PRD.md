# wespeak.ai CRM — PRD

## Problem Statement
Self-hosted, mobile-first, lightweight CRM for wespeak.ai (AI consulting company).
Runs on Hetzner. Bilingual (Hungarian + English). 5–10 users, 4 roles (admin/manager/user/guest).
Google Workspace integration (email + calendar). AI via OpenRouter (free-form text commands
create projects, contacts, deals, summaries). Storage: PostgreSQL.

## Tech Stack
- Backend: FastAPI (Python) + SQLAlchemy + PostgreSQL 15 (local, supervisor-managed)
- Frontend: React 18 (CRA, JS/JSX) + Tailwind + i18next + recharts + @hello-pangea/dnd
- Auth: JWT (httpOnly cookies), bcrypt, 4 roles
- AI: OpenRouter chat completions (user-provided key, encrypted with Fernet)

## User Personas
- Admin: manages users, settings, all data
- Manager/User: full CRUD on CRM entities
- Guest: read-only

## Core Requirements (static)
- Contacts, Companies, Deals (pipeline kanban + list), Projects, Activities/Tasks
- Dashboard with KPIs + charts
- Role-based access control
- EN/HU language switch, light/dark theme, mobile bottom-nav + desktop sidebar
- AI command bar (OpenRouter)

## Implemented (2026-07-14)
- ✅ PostgreSQL setup + supervisor persistence
- ✅ JWT auth (email/password), 4 roles, guest read-only enforcement, admin user management
- ✅ Contacts, Companies, Deals (kanban DnD + list), Projects, Activities CRUD
- ✅ Dashboard stats + charts (pipeline, contacts, upcoming tasks)
- ✅ AI command bar → OpenRouter (creates entities/answers) — needs key in Settings
- ✅ Settings page (OpenRouter key/model, Google placeholder)
- ✅ i18n EN/HU, dark/light theme, mobile-first responsive nav
- ✅ Seed data (companies, contacts, deals, projects, activities)

### Iteration 2 (2026-07-14) — P1 + P2 + Time tracking
- ✅ Entity detail pages: Contact, Company, Deal, Project — with related records + activity timelines
- ✅ Per-project time/effort tracking (TimeEntry): log hours, billable flag, billable amount (hourly_rate), logged vs estimated
- ✅ Engagement-health indicator on projects (on_track / at_risk / over_budget / completed / cancelled)
- ✅ Calendar month view for activities (prev/next, per-day tasks)
- ✅ CSV export (contacts/companies/deals/projects) + CSV import (contacts, auto-creates companies)
- ✅ Clickable list rows/cards → detail navigation
- ✅ Deployment: docker-compose, backend+frontend Dockerfiles, nginx SPA+API proxy, pg_dump backup/restore scripts, DEPLOYMENT.md (Hetzner guide), .env.example
- ✅ Tested: 35/35 backend pytest pass; all frontend flows pass

## Backlog
- P0: Google Workspace OAuth (login + Gmail + Calendar) — needs Google Cloud Client ID/Secret (user enters in Settings; scaffold ready)
- P1: OpenRouter key entry → live AI (needs user key)
- P2: TimeEntry ownership checks on delete ✅ (owner or admin/manager only); import result toast ✅; projects pagination ✅ (X-Total-Count header + batched hours, no N+1)
- P2: notifications, email logging to contacts

## Next Tasks
1. User provides OpenRouter key (in Settings) → AI live
2. User provides Google Cloud OAuth creds → implement Workspace integration
3. Optional: TS migration (robustness only, not security)
