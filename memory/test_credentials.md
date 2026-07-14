# wespeak.ai CRM — Test Credentials

Backend: FastAPI + PostgreSQL (local, port 5432, db `wespeak_crm`)
Auth: JWT via httpOnly cookies (samesite=none, secure). Login endpoint returns user + sets cookies.

## Accounts (seeded on startup)
| Role    | Email                | Password    | Access |
|---------|----------------------|-------------|--------|
| Admin   | admin@wespeak.ai     | admin123    | Full + Users + Settings |
| Manager | manager@wespeak.ai   | manager123  | Full CRUD |
| User    | user@wespeak.ai      | user123     | Full CRUD |
| Guest   | guest@wespeak.ai     | guest123    | Read-only (write blocked with 403) |

## Auth endpoints
- POST /api/auth/register  { email, password, name }
- POST /api/auth/login     { email, password }
- POST /api/auth/logout
- GET  /api/auth/me
- POST /api/auth/refresh

## Notes
- AI command endpoint POST /api/ai/command requires an OpenRouter API key set in Settings
  (admin only). Until configured it returns 400 "OpenRouter API key not configured". This is expected.
- Google Workspace (login/calendar/gmail) is NOT yet configured — requires Google Cloud OAuth credentials.
