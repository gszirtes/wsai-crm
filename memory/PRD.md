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

## Backlog
- P0: Google Workspace OAuth (login + Gmail + Calendar) — needs Google Cloud credentials
- P1: Contact/Deal/Project detail pages with linked activities timeline
- P1: Calendar view for activities
- P2: CSV import/export, email logging to contacts, notifications
- P2: Backup script + Hetzner deployment guide (docker-compose)

## Next Tasks
1. Collect OpenRouter API key from user → enable AI live
2. Collect Google Cloud OAuth creds → implement Workspace integration
3. Build entity detail pages + activity timelines
