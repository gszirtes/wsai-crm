# Full-Repo Audit — Phase 0/1 Completeness, Security, Code Quality

**Date:** 2026-07-21
**Scope:** entire repo at `main` (Phase 0 + Phase 1 of the CRM v2 migration, per `INTEGRATION_PLAN.md`), cross-checked against `feat/phase-0-foundations` and `feat/phase-1-access-control` history where relevant.
**Method:** four independent audits (Phase 0 completeness, Phase 1 completeness, security review, general code-quality/bug hunt) run in parallel against the actual code, each required to cite `file:line` evidence rather than trust `CLAUDE.md`/`AGENTS.md`/`INTEGRATION_PLAN.md` claims. The highest-severity and most surprising findings were then independently re-verified by direct file reads (noted inline as "confirmed by direct read").
**Not in scope:** fixing anything. This is a findings report; no code was changed.

---

## TL;DR

- **Phase 1 (access control)** is, in substance, very well implemented: the capability matrix, visibility filtering, financial masking, and authz-precedence rules all match `INTEGRATION_PLAN.md` and hold up under direct code inspection. Two real bugs found (service-account FK crashes), both narrow and mechanical to fix.
- **Phase 0** is 3/4 solid. The one weak sub-section (0.3, the EventLog audit trail) does *not* meet its own stated bar of "every write path logs" — several write paths still don't log, and `CLAUDE.md`/`AGENTS.md` currently assert behavior (404/"archived" on deleted-entity timeline reads) that doesn't exist in code.
- **Security**: one real, exploitable **IDOR class** — missing visibility (`can_see`) checks on two sibling endpoint groups (`activities.py` list/create, `projects.py` time entries) that every other Deal/Project-adjacent endpoint correctly has. This is the single most important finding in this audit — it was independently rediscovered by two of the four agents and confirmed by my own direct reads. Also: CSV formula injection, no rate limit on the AI command endpoint, a proxy-unaware rate-limiter IP key, and a stale-session gap on token refresh.
- **Code quality**: an N+1 query pattern in the exact code path the Phase 1 refactor touched, a capability-matrix self-lockout risk (no server-side guard keeps admin/manager capabilities non-empty), a couple of TOCTOU races, and several frontend mutations with no error handling.

---

## 1. Phase 0 — sub-section verdicts

| Sub-section | Verdict |
|---|---|
| 0.1 Alembic migration baseline | **Fully implemented.** Clean linear migration chain, `server.py` has zero `create_all`/`ALTER TABLE`, `entrypoint.sh` runs migrate→seed→serve in order, test fixture skips (not fails) without `DATABASE_URL`. |
| 0.2 `Activity.direction` | **Fully implemented.** Column, `Literal` schema, old `[Inbound]/[Outbound]` subject-prefix hack fully removed (verified by diff against pre-migration commit), i18n keys added both languages, new "Log activity" UI on `DealDetail.jsx`. |
| 0.3 EventLog audit trail | **Partially implemented — see below.** |
| 0.4 Schema hygiene | **Fully implemented.** `ProjectPriority`/`UserRole` Literals in place and used; all 58 endpoints across 14 routers have both `summary=`/`description=`; three exception handlers produce a consistent `{detail, status_code, path}` envelope; tests assert 422 (not silent fallback) for invalid role/priority.

### 0.3 in detail — the "every write path logs" claim is false

The EventLog table, index, `log_event()` helper, and the admin/manager-only `GET /api/event-logs` read endpoint are all correctly built and match the plan's schema exactly. But mapping every `POST`/`PUT`/`PATCH`/`DELETE` in the app to whether it calls `log_event()` turns up real gaps:

- **Already fixed** (Phase 1 commit `2767486`, self-documented as "a Phase 0 gap, fixed here"): all 5 entity `DELETE` endpoints now log a `deleted` event; `PUT /activities/{id}`'s completed-flip now logs, matching `PATCH /toggle`. Confirmed current — `activities.py:95-96` (`delete_activity`) does call `log_event(..., "deleted", ...)` today.
- **Still open, confirmed by direct read of current `main`:**
  - `companies.py` `PUT /companies/{id}` (lines 66-77) — no `log_event` call at all, not even conditional. Every other entity's `PUT` logs a status/stage change.
  - `users.py` — **zero** `log_event` calls anywhere in the file: user create, role/active change, delete, and `PUT /me/locale` are all unaudited. This is a real gap given `EventLog` is meant to be the audit trail and role/deactivation changes are exactly the kind of event an audit trail exists for.
  - `auth_router.py` `POST /auth/register` — creates a `User` row, doesn't log.
  - `projects.py` time-entry `add_time`/`delete_time` — don't log.
- `CLAUDE.md`/`AGENTS.md` state *"deleted entities' `/timeline` returns 404/'archived', not a dangling error"* — confirmed false by reading `backend/routers/event_logs.py` in full: `list_event_logs` does a plain filtered query with no check that the parent entity still exists, and no archived-flag logic of any kind. (The endpoint's own `description=` text is more honest about scope than the doc file is.)

**Recommendation:** either extend `log_event()` coverage to the four gaps above, or update `CLAUDE.md`/`AGENTS.md` to stop claiming universal coverage and the 404/archived behavior until it's built.

---

## 2. Phase 1 — sub-section verdicts

| Sub-section | Verdict |
|---|---|
| Capability matrix (backend + admin UI) | **Fully implemented.** 7 capabilities match the plan exactly; D6 defaults correct; `manage_users`/`configure_permissions` correctly excluded and pinned to `require_role("admin")`. UI lock on admin/manager columns is UI-only (see Finding S/BUG-1 below) but that's honestly scoped, not a false claim. |
| Object visibility (`Deal`/`Project.visibility`, D5) | **Fully implemented.** DB default `"public"`, org-wide override via `AppSetting`, respected on every creation path including the AI flow; excluded from Create/Update schemas so `PUT` can't silently change it (test-covered). |
| EntityMembership | **Implemented, with one real bug** — see Finding BUG-2 below. Owner auto-tag, owner-removal guard, and the non-admin-only `/users/directory` (role field correctly stripped) are all correct. |
| Visibility filtering (BL-2) | **Fully implemented** on every route the plan names — deals, projects, company/contact nested detail, dashboard aggregates, CSV export, *and* write endpoints (extension beyond the plan's literal text, test-covered by `test_write_endpoints_404_for_non_member_even_with_manage_deals`). **Not** implemented on two sibling routes the plan's visibility model should logically cover — see Finding SEC-1 below, the most important finding in this report. |
| Financial masking (BL-3, D2) | **Fully implemented**, pattern "A" exactly as specced: masking happens on the built `*Out` instance, never the ORM entity; every `DealOut`/`ProjectOut` construction site is masked, including nested company/contact detail, dashboard, CSV export, and utilization report (which correctly re-checks `view_financials` independently of `view_all_reports`). |
| Authz precedence (JV-13) | **Fully implemented.** No route stacks two conflicting guards; capability fully replaces role/write checks on the routes it covers, untouched elsewhere. `ai_router.py`'s `create_deal`/`create_project` correctly gate on `manage_deals`/`manage_projects` via `has_capability()`, and AI-created deals/projects now get the org-default visibility and creator membership tag (confirmed by reading `ai_router.py:74-100`). |
| ServiceAccount (MCP-enabler) | **Mostly implemented, two real bugs** — see Findings BUG-1/BUG-2. |

### Bugs found in Phase 1

**BUG-1 — `service_accounts.py:23`, `created_by=admin.id` not FK-safe against a `ServiceAccount` principal.**
`require_role("admin")` only checks `.role`, and a `ServiceAccount` can legally have `role="admin"`. If such a service account authenticates via `X-API-Key` and calls `POST /api/service-accounts`, `created_by=admin.id` writes the calling service account's id into a column FK'd to `users.id` → unhandled `ForeignKeyViolation` (no `IntegrityError` handler exists in `server.py`). Not covered by any test.

**BUG-2 — `deals.py:153`/`projects.py:189`, `add_member(..., added_by=user)` not FK-safe against a `ServiceAccount` principal.**
`membership.add_member()`'s `added_by` parameter takes the raw `.id` off whatever caller is passed, with no guard. The self-tagging calls at entity creation (`deals.py:71`, `projects.py:124`, `ai_router.py:79,100`) are correctly guarded with `isinstance(user, User)` — but the **invite endpoints** (`POST /api/deals/{id}/members`, `POST /api/projects/{id}/members`) are not. A service account whose role has `invite_members=True` (e.g. `role="manager"`, `invite_members` defaults on) calling either invite endpoint will crash the same way as BUG-1. Not covered by any test.

Both bugs share one root cause: `owner_id_for()` was applied everywhere `owner_id`/`user_id` gets set from the acting principal, but the sweep didn't reach `EntityMembership.added_by` on the invite path or `ServiceAccount.created_by`. Same mechanical fix pattern as the rest of that sweep.

**Minor/latent, not currently exploitable:** `notifications.py`'s `_sync` does `Notification(user_id=user.id, ...)` with no `isinstance` guard — currently safe only because `owner_id_for()` guarantees a `ServiceAccount` never owns an `Activity`/`Project` in the first place, so the notification-building code path never runs for one. This is an implicit invariant, not an explicit guard — worth a comment or an explicit check if the invariant is ever relaxed.

**Minor, self-disclosed, not a bug:** the admin/manager capability lock (`Settings.jsx` rendering those columns as read-only ticks) is UI-only — see SEC/BUG overlap finding below for the server-side implication.

---

## 3. Security findings

Ranked by severity. IDOR (SEC-1) is the standout; the rest are real but narrower.

### SEC-1 (High) — Missing visibility checks on two sibling endpoint groups: confirmed IDOR

Every Deal/Project-adjacent read/write endpoint in the app gates on `can_see(db, "deal"/"project", obj, user)` before returning or mutating anything — **except** two groups that were apparently missed by the Phase 1 refactor:

- **`activities.py::list_activities`** (`GET /api/activities?deal_id=...&project_id=...`) and **`create_activity`** — no import of `visibility_filter`/`can_see` anywhere in the file, only `get_current_user`/`require_write`. Confirmed by direct read: the query filters on `deal_id`/`project_id` with zero existence or visibility check. **Any authenticated user, including a guest, can `GET /api/activities?deal_id=<private-deal-id>` and read every activity (subject, description, due date, completion status) tied to a deal that is otherwise a 404 to them on every other endpoint.** `create_activity` has the write-side mirror: it accepts any `deal_id`/`project_id` in the payload with no check, so a user can attach activities (and their audit-logged `activity_logged` events) to a private deal they can't see.
- **`projects.py`'s time-entry sub-resource** (`list_time`, `add_time`, `delete_time`) — confirmed by direct read (`projects.py:216-260` and follow-up read of the `delete_time` region): only `add_time` checks the project *exists*, none check `can_see`. A non-member, non-admin/manager user who knows a private project's id can read or fabricate hours against it via direct API calls, even though `GET /api/projects/{id}` correctly 404s for the same user. Not reachable via normal UI navigation (the frontend only gets there after a page load that already required visibility), but fully reachable via direct API/curl/an MCP service-account key.

Both were independently flagged by two of the four audit agents (security review and general bug hunt) without cross-contamination, which is a strong signal this is real rather than a false positive — and I confirmed both directly by reading the source.

**Recommendation:** add the same `can_see()` gate these files already use everywhere else — on `list_activities`/`create_activity` (resolve the parent deal/project first, `404` if not visible) and on all three project time-entry endpoints.

### SEC-2 (Medium) — CSV formula injection (CWE-1236) in exports

`data_io.py::_csv_response` writes user-controlled string fields (deal/project/contact/company names, etc.) directly into CSV cells with no leading-character sanitization. A field value starting with `=`, `+`, `-`, or `@` (e.g. a contact name of `=cmd|'/c calc'!A1`) will be interpreted as a formula by Excel/Sheets when the export is opened. Standard mitigation: prefix such values with a `'` or tab before writing.

### SEC-3 (Medium/High) — `POST /api/ai/command` has no endpoint-specific rate limit

Every other write-heavy or auth-adjacent endpoint has rate limiting; the AI command endpoint (which makes an outbound OpenRouter call per request, i.e. has real per-request cost and a slower response time that's easy to pile up) does not appear to have one applied. Worth confirming against `rate_limit.py`'s actual decorator list and adding one if genuinely absent.

### SEC-4 (Medium) — Rate limiter's IP resolution likely broken behind the nginx proxy

`slowapi`'s default `get_remote_address` key function reads the TCP peer address, which behind nginx will be the proxy's own address for every request unless `X-Forwarded-For` is explicitly trusted and parsed. If so, rate limiting is effectively a shared bucket across all real users rather than per-client — worth verifying against the actual nginx config and switching to a proxy-aware key function if confirmed.

### SEC-5 (Low) — `POST /api/auth/refresh` doesn't check `user.active`

A deactivated user holding a still-valid refresh token cookie can mint a fresh access token. Given access tokens live 12h and refresh tokens 7d, this is a real (if narrow) gap in the deactivation story — `active` should be re-checked at refresh time, not just at login.

### SEC-6 (Informational) — Upstream/internal error text forwarded verbatim

`ai_router.py:131-134` / `ai_service.py:83` do `raise HTTPException(status_code=502, detail=str(e))`, forwarding OpenRouter's raw response body or a Python exception message straight to the client. No secrets leak (the API key never appears in these paths), but it's inconsistent with the app's otherwise-structured error envelope and could leak internal detail. Confirmed by direct read of `ai_router.py`.

### SEC-7 (Informational) — `reassign_owner` capability defined but never enforced

Fully modeled in `ALL_CAPABILITIES`, `DEFAULT_CAPABILITIES`, the `CapabilityMatrix` schema, and the admin Settings UI — but `grep -rn "reassign_owner" backend/routers` returns nothing. There is no owner-reassignment endpoint at all yet. Toggling this in the admin UI currently has zero effect. Independently flagged by both the security and bug-hunt agents. Likely intentional (owner reassignment is plausibly later-phase scope), but the UI currently implies a live control that does nothing — worth either wiring it up or greying it out with a "not yet implemented" note.

---

## 4. Code-quality / bug-hunt findings

### BUG-3 (Medium) — Capability matrix has no server-side guard against locking out admin/manager

`get_capability_matrix()` (`capabilities.py:45-59`) merges *stored* JSON straight over the coded defaults for **every** role, including `admin`/`manager` — confirmed by direct read. `PUT /api/settings/capabilities` (`settings_router.py:48-54`) accepts and persists a full matrix with no check that `admin`/`manager` stay all-`True`. The current admin UI (`Settings.jsx`) renders those two columns as read-only ticks, so this can't happen through the normal UI *today* — but since `manage_deals`/`manage_projects`/etc. are capability-gated rather than role-gated, a raw API call (or any future "reset to defaults"-style UI bug that round-trips a stale matrix) could set `admin.manage_deals=False` and lock every admin out of deal/project writes, with no break-glass path except a manual DB edit. Recommend: reject or silently force `admin`/`manager` rows to all-`True` server-side in `update_capabilities`, not just in the UI.

### BUG-4 (Medium) — N+1 capability-matrix fetch in deal/project list and nested detail endpoints

`mask_deal_out`/`mask_project_out` → `can_view_financials` → `get_capability_matrix(db)` re-queries `AppSetting` **on every row** inside `deals.py`'s list comprehension (`_to_out` per deal), `projects.py`'s equivalent, and the nested deals/projects in `company_detail`/`contact_detail`. This is a real regression relative to the sibling code written in the *same* refactor: `data_io.py`'s CSV export and `reports.py`'s utilization report both correctly hoist `can_see_money = can_view_financials(db, user)` once outside their loops. Fix: do the same in `deals.py`/`projects.py`/`companies.py`/`contacts.py`.

### BUG-5 (Medium) — `EntityMembership.add_member` TOCTOU race → unhandled `IntegrityError`

Check-then-insert with no transaction-level guard; two concurrent invites of the same user hit the `uq_entity_membership` unique constraint on the second commit, surfacing as an unhandled 500 rather than the intended idempotent success. Low likelihood in a 5-10 user team, but a one-line `try/except IntegrityError: db.rollback(); return existing` would close it.

### BUG-6 (Low-Medium) — CSV contact import: TOCTOU on duplicate-email check, and split commit timing

`data_io.py::import_contacts` loads `existing_emails` once before the loop (no DB-level unique constraint on `Contact.email` to backstop it, unlike `User.email`), and auto-created companies are committed immediately mid-loop while contacts are only flushed until one final commit at the end — a mid-loop failure would leave orphan companies with no matching contacts. Narrow trigger condition (duplicate emails and missing-name rows are already handled gracefully via `continue`, not exceptions), but worth tightening for consistency.

### BUG-7 (Low) — `export_contacts` missing the `joinedload` that `list_contacts` already has

`data_io.py:34-40` lazy-loads `c.company.name` per row with no `joinedload(Contact.company)`, unlike `contacts.py:33`'s list endpoint which was already fixed for exactly this pattern — an N+1 the same refactor solved in one place and missed in its sibling.

### Frontend (Medium, cluster) — mutating calls with no error handling, some with unrolled optimistic updates

- `VisibilityMembers.jsx` — every mutating call (`load`, `toggleVisibility`, invite, remove) has no `.catch`; a failed toggle silently no-ops with no user feedback.
- `Settings.jsx::saveDefaultVisibility`/`save`/`saveCapabilities` — state updated optimistically before the request resolves, no rollback on failure, so a failed save can leave the UI showing a value the backend never persisted.
- `Deals.jsx`'s kanban drag-and-drop — optimistically moves the card, then `await`s the stage-change PATCH with no catch; a failed request leaves the card in the wrong column until manual refresh.
- Broader, pre-existing pattern (not introduced by Phase 1): most list-page `useEffect` fetches use `.then()` with no `.catch()`, unlike the `*Detail.jsx` pages which correctly redirect on failure. A 401/500 on any list page leaves it stuck on a stale/loading state with no visible error.

### Dead code / consistency
- `reassign_owner` — see SEC-7 above (cross-referenced from both angles independently, strong signal).
- `test_phase1.py` has a small duplicated helper (`_user_id_by_email` module function vs. `TestEntityMembership._other_user_id`) — trivial, low priority.
- No unused imports found in any of the recently-touched Phase 1 modules — the sweep was otherwise clean.

### Test suite health
- Every test wraps assertions in `try/finally` cleanup, so a failed assertion doesn't skip teardown.
- Several Phase 1 test classes mutate the single global `role_capabilities` `AppSetting` row and restore it in `finally` — safe under the documented sequential `pytest -v` invocation, but would race under `pytest-xdist`/parallel execution (not currently used, per `CLAUDE.md`, so this is a latent risk, not an active bug).

---

## 5. Consolidated priority list

| # | Finding | Area | Severity | Fix effort |
|---|---|---|---|---|
| 1 | SEC-1: missing `can_see` on `activities.py` list/create and `projects.py` time endpoints | Security / IDOR | **High** | Small — mirror the existing `can_see` pattern already used everywhere else in the same files |
| 2 | BUG-1/BUG-2: unguarded FK writes (`created_by`, `added_by`) for ServiceAccount principals | Security / crash | Medium-High (crashes, not data leak) | Small — apply `owner_id_for()`-style guard, same pattern already used elsewhere |
| 3 | SEC-2: CSV formula injection | Security | Medium | Small — prefix-sanitize on export |
| 4 | BUG-3: no server-side floor on admin/manager capabilities | Security / self-lockout | Medium | Small |
| 5 | 0.3: EventLog gaps (`companies.py PUT`, `users.py`, `auth_router.py register`, project time entries) + false doc claim | Phase 0 completeness | Medium | Medium — several call sites, plus a doc correction |
| 6 | SEC-3/SEC-4: AI endpoint rate limit + proxy-aware IP key | Security | Medium | Small-Medium, needs `rate_limit.py`/nginx config check first |
| 7 | BUG-4: N+1 capability-matrix fetch | Performance | Medium | Small — hoist one call per endpoint, same pattern as `data_io.py`/`reports.py` |
| 8 | BUG-5: `add_member` TOCTOU | Correctness | Medium | Small |
| 9 | Frontend error-handling cluster | Correctness/UX | Medium | Medium — several files, same fix pattern |
| 10 | SEC-5: refresh doesn't check `active` | Security | Low | Small |
| 11 | BUG-6/BUG-7: CSV import commit ordering, missing joinedload | Correctness/perf | Low | Small |
| 12 | SEC-6, SEC-7: error-text leak, unenforced `reassign_owner` | Informational | Low | Small / product decision |

---

## 6. What's genuinely solid (confirmed, not just claimed)

To avoid over-indexing on the gaps: the bulk of Phase 1's access-control surface is well-built and matches the plan precisely on direct inspection —

- Financial masking (pattern A) is applied at every `*Out` construction site plus every non-schema surface the plan calls out (dashboard, CSV, utilization), with the utilization report correctly treating `view_financials` and `view_all_reports` as independent gates.
- Visibility filtering is applied consistently across list/detail/write endpoints for Deal/Project themselves, including the write-path extension beyond the plan's literal text (test-covered).
- The AI command flow's capability check, default-visibility assignment, and creator-membership-tagging are all genuinely fixed, not just claimed in a commit message.
- Object-visibility exclusion from Create/Update schemas is real and test-covered — `PUT` cannot silently flip `visibility`.
- Migration/seed bootstrap ordering, schema hygiene (Literals, structured error envelope), and Activity.direction are all fully and correctly implemented with no gaps found.
