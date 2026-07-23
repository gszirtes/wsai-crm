# wespeak.ai CRM — Deployment on Hetzner

Self-hosted, mobile-first CRM. Stack: FastAPI + PostgreSQL + React, shipped as Docker containers.

## 1. Prerequisites (Hetzner Cloud)
- A Hetzner Cloud server (CX22 / 2 vCPU / 4 GB RAM is plenty for 5–10 users), Ubuntu 24.04.
- A domain pointed at the server (e.g. `crm.wespeak.ai`).
- Docker + Docker Compose:
  ```bash
  curl -fsSL https://get.docker.com | sh
  ```

## 2. Get the code & configure
```bash
git clone <your-repo> /opt/wespeak-crm && cd /opt/wespeak-crm
cp .env.example .env
```
Edit `.env` and set strong secrets:
```bash
python3 -c "import secrets; print('JWT_SECRET='+secrets.token_hex(48))"
python3 -c "from cryptography.fernet import Fernet; print('FERNET_KEY='+Fernet.generate_key().decode())"
```
Set `FRONTEND_URL` to your public HTTPS URL (needed for CORS + secure cookies) and set a strong
`POSTGRES_PASSWORD` and `ADMIN_PASSWORD`.

Additional env vars (see `.env.example` for details):
- `COOKIE_SECURE=true` — required for HTTPS (cookies won't work over HTTP otherwise)
- `ALLOW_REGISTRATION=false` — keeps self-registration off (default)
- `RATE_LIMITING_ENABLED=true` — keeps brute-force protection on (default)

## 3. Launch
```bash
docker compose up -d --build
```
- Frontend: served by nginx on port 3000 (proxies `/api` to the backend).
- Backend: FastAPI on 127.0.0.1:8001 (not publicly exposed).
- DB: PostgreSQL with a persistent `pgdata` volume.

The backend auto-creates tables and seeds the admin account on first start.

## 4. TLS / reverse proxy
Put Caddy or Nginx + Let's Encrypt in front for HTTPS. Minimal Caddy example (`/etc/caddy/Caddyfile`):
```
crm.wespeak.ai {
    reverse_proxy localhost:3000
}
```
> HTTPS is required: auth cookies use `Secure; SameSite=None`.

## 5. Integrations (set later in the app — no keys leave your server)
- **OpenRouter (AI):** log in as admin → Settings → paste your OpenRouter key. It is encrypted
  (Fernet) in your own DB and used only server-side. Get a free key at https://openrouter.ai/keys
- **Google Workspace (login + Gmail + Calendar):** create OAuth credentials in Google Cloud Console,
  then add Client ID/Secret in Settings (integration scaffold ready; wiring pending your credentials).

## 6. Backups (automated)
Scheduled `pg_dump` with rotation:
```bash
chmod +x scripts/backup.sh scripts/restore.sh
# Run daily at 02:30 via cron (runs inside the db container's network):
crontab -e
30 2 * * * cd /opt/wespeak-crm && POSTGRES_PASSWORD=$(grep POSTGRES_PASSWORD .env|cut -d= -f2) \
  DB_HOST=localhost BACKUP_DIR=/opt/wespeak-crm/backups docker compose exec -T db \
  pg_dump -U crm_user wespeak_crm | gzip > backups/wespeak_crm_$(date +\%Y\%m\%d).sql.gz
```
Or run the provided script from the host with `DB_HOST=localhost` (DB port is bound to localhost).
Restore: `./scripts/restore.sh backups/wespeak_crm_YYYYMMDD.sql.gz`.

Copy backups off-box (Hetzner Storage Box / S3) for disaster recovery.

## 7. Updates
```bash
git pull && docker compose up -d --build
```

## 8. MCP server (AI-native access, optional)
A separate `mcp-server` container exposes a bounded set of CRM operations
(list/search leads, deals, projects; read a deal's timeline or pipeline
analytics; create a lead, claim, change stage, log an activity, set a
milestone's status) to an external AI agent over MCP. It talks to the
CRM's own REST API — never the database directly — so every capability
check, visibility rule, and financial-masking dependency it's subject to
is identical to what a human user with the same role would see.

To turn it on:
1. Log in as admin → **Settings → Service accounts** → **New service account**.
   Pick a role the same way you would for a human user (its capabilities
   come from the same admin-configurable matrix). Copy the API key shown —
   it's never shown again.
2. Set `CRM_MCP_API_KEY=<that key>` in `.env`.
3. `docker compose up -d --build mcp-server`

The server listens on `127.0.0.1:8100` (not publicly exposed by default —
put it behind the same reverse proxy as the frontend if an external agent
needs to reach it over HTTPS). Point your MCP client at
`http://<host>:8100/mcp`.

Least-privilege note: give the service account only the capabilities the
agent actually needs (e.g. `manage_deals` for lead creation, `view_financials`
only if the agent should see deal values). Every write the agent makes is
logged to the same EventLog audit trail as a human write, attributed to
this service account (`actor_type="service"`), so `GET /api/event-logs`
shows exactly what the agent did.

## Roles
admin (full + users + settings), manager & user (full CRUD), guest (read-only).
Seeded demo accounts are listed on the login screen — change/remove them for production.
