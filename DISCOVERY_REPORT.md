# wespeak.ai CRM — Állapotfelmérés (read-only kód-audit)

> Ez a dokumentum kizárólag a repóban *ténylegesen megvalósított* állapotot írja le, forráshivatkozásokkal (`fájl:sor`). Nem tartalmaz értékelést, kritikát vagy javaslatot. Ahol a kód nem egyértelmű, ott explicit "nem egyértelmű a kódból" jelölés szerepel — ezek a riport végén, a "Nem egyértelmű pontok" szakaszban is összegyűjtve vannak.

---

## 1. Áttekintés

### Tech stack

| Réteg | Technológia | Forrás |
|---|---|---|
| Backend | Python 3, FastAPI 0.110.1, SQLAlchemy 2.0.51, Pydantic v2 (2.13.4), uvicorn 0.25.0 | `backend/requirements.txt:1-9` |
| Adatbázis | PostgreSQL 15 (Alpine), driver: psycopg2-binary | `backend/requirements.txt:9`, `docker-compose.yml:3` |
| Auth | PyJWT 2.13.0 (HS256), bcrypt 4.1.3, cryptography 49.0.0 (Fernet) | `backend/requirements.txt:16-18` |
| Rate limiting | slowapi 0.1.9 | `backend/requirements.txt:24` |
| AI kliens | httpx 0.28.1 (OpenRouter chat completions HTTP hívás) | `backend/requirements.txt:21` |
| Tesztelés | pytest 9.1.1 + requests 2.34.2 (élő szerver elleni integrációs tesztek) | `backend/requirements.txt:27-28` |
| Frontend | React 18.3.1 (CRA / react-scripts 5.0.1, JS/JSX, nem TS) | `frontend/package.json:10-14` |
| Frontend libek | Tailwind CSS 3.4.17, i18next 24.2.1 + react-i18next 15.4.0, recharts 2.15.0, @hello-pangea/dnd 17.0.0 (drag&drop), lucide-react 0.469.0 (ikonok), axios 1.7.9, react-router-dom 7.1.1 | `frontend/package.json:6-15` |
| Deployment | Docker Compose (3 service: `db`, `backend`, `frontend`), nginx reverse proxy a frontend konténerben | `docker-compose.yml`, `frontend/nginx.conf` |

### Repó/mappa struktúra

```
backend/
  server.py            — FastAPI app, CORS, router regisztráció, startup seed()
  database.py           — SQLAlchemy engine/session, get_db dependency
  models.py              — 10 SQLAlchemy modell (ORM)
  schemas.py              — Pydantic request/response sémák, Literal enumok
  auth.py                  — JWT, bcrypt, cookie-kezelés, RBAC dependency-k
  ai_service.py             — OpenRouter hívás, Fernet titkosítás
  rate_limit.py              — slowapi Limiter
  utils.py                    — logged_hours_for() megosztott segédfüggvény
  routers/                      — 12 router fájl (1 fájl / entitás), ld. 9. szakasz
  tests/                          — pytest integrációs tesztek (élő szerver ellen)
frontend/src/
  App.js                — route definíciók, Protected wrapper
  auth.jsx                — AuthProvider context, useAuth hook
  api.js                    — közös axios instance, formatApiError
  i18n.js                    — EN/HU fordítási szótárak inline
  pages/                        — 15 oldal-komponens (lista/kanban/detail nézetek)
  components/                    — Layout, AICommandBar, NotificationBell, common UI
  context/                          — NotificationContext (megosztott értesítés state)
```
Forrás: `backend/server.py:1-51`, `backend/database.py`, `frontend/src/App.js`, README.md 81-116. sor.

### Indítás / futtatás

- **Lokális fejlesztés**: backend `uvicorn server:app --reload --port 8001` a `DATABASE_URL`, `JWT_SECRET`, `FERNET_KEY` env változókkal; frontend `REACT_APP_BACKEND_URL=http://localhost:8001 npm start` (`README.md:136-150`, `CLAUDE.md` Commands szakasz).
- **Docker Compose (production)**: `docker compose up -d --build`, 3 service (`db`: postgres:15-alpine; `backend`: FastAPI/uvicorn, csak `127.0.0.1:8010:8001`-re nyitva; `frontend`: nginx, `3010:80`) — `docker-compose.yml:1-51`.
- **Séma létrehozás**: nincs Alembic, a táblák a `Base.metadata.create_all(bind=engine)` hívással jönnek létre minden induláskor (`backend/server.py:54`), plusz 2 idempotens `ALTER TABLE` (ld. 2. szakasz).
- **Seed adatok**: admin + 3 demo user + minta cégek/kontaktok/dealek/projektek/aktivitások, de csak ha még nem léteznek (`backend/server.py:53-136`).

---

## 2. Adatmodell

10 SQLAlchemy modell található a `backend/models.py`-ban, mind string UUID elsődleges kulccsal (`gen_id()`, `models.py:11-12`). Nincs Alembic migrációs mappa a repóban.

### User (`users` tábla) — `backend/models.py:19-32`

| Mező | Típus | Megjegyzés |
|---|---|---|
| id | String PK | `gen_id()` |
| email | String, unique, not null, indexelt | |
| password_hash | String, nullable | |
| name | String, not null | |
| role | String, default `"user"` | enum kommentben: `admin, manager, user, guest` |
| avatar_url | String, nullable | — lásd 11. szakasz, sehol nincs kitöltve/kiolvasva |
| locale | String, default `"en"` | |
| auth_provider | String, default `"local"` | kommentben: `local, google` |
| google_connected | Boolean, default False | — lásd 11. szakasz |
| google_email | String, nullable | — lásd 11. szakasz |
| active | Boolean, default True | |
| created_at | DateTime(tz) | |

### Company (`companies`) — `models.py:35-50`

| Mező | Típus |
|---|---|
| id | String PK |
| name | String, not null, indexelt |
| industry, website, phone, email, address, size | String, nullable |
| notes | Text, nullable |
| owner_id | FK → `users.id`, `ON DELETE SET NULL`, nullable |
| created_at, updated_at | DateTime(tz) |

Kapcsolat: `contacts = relationship("Contact", back_populates="company")` (`models.py:50`) — 1:N Company→Contact, explicit ORM relationship mindkét oldalon.

### Contact (`contacts`) — `models.py:53-69`

| Mező | Típus |
|---|---|
| id | String PK |
| first_name | String, not null |
| last_name, email (indexelt), phone, title | String, nullable |
| status | String, default `"lead"` — enum kommentben: `lead, prospect, customer, inactive` |
| tags | JSONB, default `list` (üres lista) |
| notes | Text, nullable |
| company_id | FK → `companies.id`, SET NULL |
| owner_id | FK → `users.id`, SET NULL |
| created_at, updated_at | DateTime(tz) |

Kapcsolat: `company = relationship("Company", back_populates="contacts")` (`models.py:69`).

### Deal (`deals`) — `models.py:72-86`

| Mező | Típus |
|---|---|
| id | String PK |
| title | String, not null |
| value | Float, default 0 |
| currency | String, default `"EUR"` |
| stage | String, default `"lead"` — enum kommentben: `lead, qualified, proposal, negotiation, won, lost` |
| probability | Integer, default 10 |
| expected_close | DateTime(tz), nullable |
| notes | Text, nullable |
| company_id | FK → `companies.id`, SET NULL |
| contact_id | FK → `contacts.id`, SET NULL |
| owner_id | FK → `users.id`, SET NULL |
| created_at, updated_at | DateTime(tz) |

Nincs explicit `relationship()` deklaráció ezen a modellen (csak nyers FK oszlopok). **Nincs `project_id`/`deal_id` kapcsolat Project felé** — a Deal és a Project modell között semmilyen FK vagy kapcsolat nincs definiálva.

### Project (`projects`) — `models.py:89-106`

| Mező | Típus |
|---|---|
| id | String PK |
| name | String, not null |
| description | Text, nullable |
| status | String, default `"planning"` — enum kommentben: `planning, active, on_hold, completed, cancelled` |
| priority | String, default `"medium"` — enum kommentben: `low, medium, high` |
| budget | Float, default 0 |
| estimated_hours | Float, default 0 | *(utólag hozzáadva migrációval, ld. lentebb)* |
| hourly_rate | Float, default 0 | *(utólag hozzáadva migrációval, ld. lentebb)* |
| currency | String, default `"EUR"` |
| start_date, end_date | DateTime(tz), nullable |
| company_id | FK → `companies.id`, SET NULL |
| contact_id | FK → `contacts.id`, SET NULL |
| owner_id | FK → `users.id`, SET NULL |
| created_at, updated_at | DateTime(tz) |

### Activity (`activities`) — `models.py:109-122`

| Mező | Típus |
|---|---|
| id | String PK |
| type | String, default `"task"` — enum kommentben: `call, email, meeting, task, note` |
| subject | String, not null |
| description | Text, nullable |
| due_date | DateTime(tz), nullable |
| completed | Boolean, default False |
| contact_id | FK → `contacts.id`, SET NULL |
| company_id | FK → `companies.id`, SET NULL |
| deal_id | FK → `deals.id`, SET NULL |
| project_id | FK → `projects.id`, SET NULL |
| owner_id | FK → `users.id`, SET NULL |
| created_at | DateTime(tz) |

Egy Activity egyszerre kapcsolódhat kontakthoz, céghez, dealhez ÉS projekthez is (mind a 4 FK nullable, egyik sem kizárja a másikat kód szinten) — nincs polimorf "egy szülő" megkötés a kódban.

### TimeEntry (`time_entries`) — `models.py:125-134`

| Mező | Típus |
|---|---|
| id | String PK |
| project_id | FK → `projects.id`, **ON DELETE CASCADE**, not null, indexelt |
| user_id | FK → `users.id`, SET NULL, nullable |
| hours | Float, default 0 |
| description | String, nullable |
| billable | Boolean, default True |
| entry_date | DateTime(tz), default most |
| created_at | DateTime(tz) |

### Notification (`notifications`) — `models.py:137-147`

| Mező | Típus |
|---|---|
| id | String PK |
| user_id | FK → `users.id`, **ON DELETE CASCADE**, indexelt |
| key | String, indexelt (dedup kulcs, pl. `"overdue:{activity_id}"`) |
| type | String, default `"info"` — kommentben: `auto_overdue, auto_due_today, auto_project_risk, info` |
| title | String, not null |
| body, link | String, nullable |
| read | Boolean, default False |
| created_at | DateTime(tz) |

### AppSetting (`app_settings`) — `models.py:150-153`

Egyszerű kulcs-érték tár: `key` (String PK), `value` (Text, nullable). Ténylegesen használt kulcsok: `openrouter_api_key` (Fernet-titkosítva), `openrouter_model` (`backend/ai_service.py`, `backend/routers/settings_router.py`).

### AICommandLog (`ai_command_logs`) — `models.py:156-163`

| Mező | Típus |
|---|---|
| id | String PK |
| user_id | FK → `users.id`, SET NULL, nullable |
| command | Text, not null |
| action | String, nullable |
| response | Text, nullable |
| created_at | DateTime(tz) |

### Kapcsolatok összefoglalása

| Kapcsolat | Típus | Definiálva |
|---|---|---|
| Company → Contact | 1:N | FK `Contact.company_id` + explicit `relationship()` mindkét oldalon (`models.py:50,69`) |
| Company → Deal / Project / Activity | 1:N | csak nyers FK oszlop (`company_id`), nincs `relationship()` |
| Contact → Deal / Project / Activity | 1:N | csak nyers FK oszlop (`contact_id`) |
| Deal → Activity | 1:N | csak nyers FK oszlop (`deal_id`) |
| Project → Activity | 1:N | csak nyers FK oszlop (`project_id`) |
| Project → TimeEntry | 1:N | FK `TimeEntry.project_id`, CASCADE |
| User → Company/Contact/Deal/Project/Activity | 1:N ("owner") | `owner_id` FK, SET NULL, csak nyers FK oszlop mind az 5 modellen |
| User → TimeEntry | 1:N | `TimeEntry.user_id`, SET NULL |
| User → Notification | 1:N | `Notification.user_id`, CASCADE |
| User → AICommandLog | 1:N | `AICommandLog.user_id`, SET NULL |
| Deal ↔ Project | **nincs kapcsolat** | nincs FK egyik irányban sem |

Nincs N:M kapcsolat sehol a kódbázisban (nincs join tábla). Nincs önhivatkozó (self-referential) FK egyetlen modellen sem (pl. nincs "kontakt beajánlott egy másik kontaktot" jellegű kapcsolat — ld. 7. szakasz).

### Enum / választható érték listák (a Pydantic `Literal` a tényleges, kikényszerített forrás — `backend/schemas.py:6-9`)

| Mező | Modell | Pontos értékek | Forrás |
|---|---|---|---|
| `stage` | Deal | `lead, qualified, proposal, negotiation, won, lost` | `schemas.py:6`, `models.py:78` |
| `status` | Contact | `lead, prospect, customer, inactive` | `schemas.py:7`, `models.py:61` |
| `status` | Project | `planning, active, on_hold, completed, cancelled` | `schemas.py:8`, `models.py:94` |
| `type` | Activity | `call, email, meeting, task, note` | `schemas.py:9`, `models.py:112` |
| `priority` | Project | `low, medium, high` | csak `models.py:95` kommentben és `backend/routers/ai_router.py:15` `VALID_PRIORITIES` halmazban — **`schemas.py`-ban `priority: Optional[str]` szabad string, nincs `Literal` típus rajta** (`schemas.py:136`) |
| `role` | User | `admin, manager, user, guest` | `backend/auth.py:12` (`ROLE_LEVELS` dict kulcsai), `backend/routers/users.py:10` (`VALID_ROLES`) — **`schemas.py`-ban sincs `Literal` a `role`-on**, `RegisterRequest.role: Optional[str] = "user"` (`schemas.py:17`) szabad string |
| `type` | Notification | `auto_overdue, auto_due_today, auto_project_risk, info` | `models.py:142` kommentben; a `info` értéket a kódban sehol nem hozza létre semmilyen endpoint (ld. 4. szakasz) |
| `locale` | User/LocaleUpdate | `en, hu` | `schemas.py:221` (`Literal["en","hu"]`) |

**Megjegyzés**: a `Project.priority` és a `User.role` mezőkön — a `CLAUDE.md` "Security-sensitive defaults" szakaszában rögzített elvárással szemben (minden enum-szerű mezőnek legyen Pydantic `Literal`-ja) — nincs `Literal` típus a `schemas.py`-ban; ezek a kódban máshol (routerekben) definiált halmazok (`VALID_PRIORITIES`, `VALID_ROLES`) ellen vannak csak validálva, nem a Pydantic rétegben.

### Soft delete / audit log / verziózás

**Egyik sem található egyik modellen sem.** Nincs `is_deleted`, `deleted_at`, `version`, `history`, audit-log tábla vagy hasonló mező sehol a `models.py`-ban (164 sor, teljes fájl átnézve). Minden törlés hard delete (`db.delete(...)`), gyerek FK-k explicit nullázásával vagy DB-szintű cascade-del (ld. 3. szakasz). Nincs `updated_by`/`created_by` mező sem — csak `owner_id` létezik "ki a felelős" jelleggel, nem audit céllal.

### Ad-hoc migrációk (nincs Alembic)

`backend/server.py:56-59` (`seed()` függvényen belül, minden induláskor lefut, idempotens `IF NOT EXISTS`):
```sql
ALTER TABLE projects ADD COLUMN IF NOT EXISTS estimated_hours DOUBLE PRECISION DEFAULT 0
ALTER TABLE projects ADD COLUMN IF NOT EXISTS hourly_rate DOUBLE PRECISION DEFAULT 0
```
Ez a két oszlop utólag került a `Project` táblához egy meglévő telepítés frissítéseként. Mindkettő ténylegesen használt (nem holt mező) — ld. 11. szakasz.

### Owner mező

`owner_id` az 5 fő entitáson (`Company`, `Contact`, `Deal`, `Project`, `Activity`) — mindegyik nullable FK `users.id`-ra, `SET NULL` törléskor (`models.py:46,65,84,104,121`). Kitöltés módja: ld. 3. szakasz.

### backend/utils.py

Egyetlen segédfüggvény: `logged_hours_for(db, project_id)` (`backend/utils.py:6-9`) — az adott projekthez tartozó összes `TimeEntry.hours` összegét adja vissza (`SUM`, `COALESCE(...,0)`), billable-szűrés **nélkül** (az teljes logolt óraszám, nem csak a számlázható). Ezt használja a `notifications.py` (over-budget ellenőrzés) és korábban valószínűleg a `projects.py` is (a `projects.py` a billable órákat külön, saját `SUM ... WHERE billable=True` lekérdezéssel számolja — `backend/routers/projects.py:88-90` — nem a shared util-lal).

---

## 3. Üzleti logika / állapotgépek

### Stádium/státusz mezők és értékeik

Ld. a 2. szakasz enum-táblázatát: `Deal.stage`, `Contact.status`, `Project.status`, `Activity.type`, `Activity.completed` (bool), `Notification.read` (bool), `User.role`, `User.active` (bool).

### Átmeneti szabályok

**Nem található egyetlen állapotgép-szerű átmenet-védelem (guard) sem a kódban egyik mezőn sem.** Minden stádium-/enum-mező kizárólag a megengedett érték-halmaz ellen van validálva (Pydantic `Literal` vagy egy `VALID_X` halmaz ellenőrzés a routerben), majd közvetlenül hozzárendelve (`setattr`/direkt attribútum-írás) — **nincs "X állapotból csak Y-ba léphet" jellegű logika sehol**:

- **Deal.stage**: `PATCH /api/deals/{id}/stage` (`backend/routers/deals.py:73-83`) — bármelyik authentikált write-jogú felhasználó bármelyik stádiumból bármelyik másikba átteheti a dealt egyetlen hívással (pl. `won` → `lead`, `lost` → `won` is engedélyezett). Csak a `StageUpdate.stage: DealStage` Pydantic típus ellenőrzi, hogy a *cél* érték szerepel-e az engedélyezett listában — a *jelenlegi* értéket sosem nézi meg a kód. A `PUT /api/deals/{id}` (teljes update, `deals.py:60-70`) generikus `setattr` ciklussal ugyanígy bármire állítható.
- **Contact.status**: `PUT /api/contacts/{id}` (`backend/routers/contacts.py:70-80`) generikus `setattr` ciklus, nincs átmenet-korlátozás (`customer` → `lead` is engedélyezett).
- **Project.status**: `PUT /api/projects/{id}` (`backend/routers/projects.py:119-127`) generikus `setattr` ciklus, nincs korlátozás (`completed` → `planning` is engedélyezett).
- **Activity.completed**: `PATCH /api/activities/{id}/toggle` (`backend/routers/activities.py:51-60`) feltétel nélkül invertálja (`a.completed = not a.completed`).
- **Notification.read**: csak egyirányú "olvasottá jelölés" végpont létezik (`POST /{id}/read`, `POST /read-all` — `backend/routers/notifications.py:85-102`), nincs "olvasatlanná visszaállítás" végpont, tehát itt guard-ra nincs is szükség a jelenlegi API felszínen.
- **User.role**: `PUT /api/users/{id}` (`backend/routers/users.py:35-58`) csak azt ellenőrzi, hogy az új érték szerepel-e a `VALID_ROLES` halmazban; bármelyik admin bármelyik felhasználót bármelyik szerepkörbe áthelyezheti — az egyetlen kivétel egy azonosság-védelem: egy admin nem fokozhatja le saját magát és nem tilthatja le saját magát (`users.py:42-43,48-49`), ami nem szekvenciális állapotgép-szabály, hanem önvédelmi ellenőrzés.

### Owner mező kitöltése

Az `owner_id` mind az 5 entitáson (`Company`, `Contact`, `Deal`, `Project`, `Activity`) **teljesen ki van zárva** a create/update Pydantic sémákból (`CompanyBase`, `ContactBase`, `DealBase`, `ProjectBase`, `ActivityBase` — `schemas.py:50-59,75-84,102-111,132-144,185-194` — egyik sem deklarál `owner_id` mezőt), tehát kliens oldalról sosem érkezhet be inputként. Mindig szerver oldalon, automatikusan az aktuális bejelentkezett userre van állítva létrehozáskor:

```python
Company(**payload.model_dump(), owner_id=user.id)   # backend/routers/companies.py:49
Contact(**payload.model_dump(), owner_id=user.id)    # backend/routers/contacts.py:61
Deal(**payload.model_dump(), owner_id=user.id)       # backend/routers/deals.py:53
Project(**payload.model_dump(), owner_id=user.id)    # backend/routers/projects.py:110
Activity(**payload.model_dump(), owner_id=user.id)   # backend/routers/activities.py:31
```
Update (`PUT`) végpontok nem írják felül, mert az update séma sem tartalmazza a mezőt — tehát az owner a létrehozó userre van rögzítve, és update-tel sosem változtatható át máshoz egyik routeren keresztül sem. Az AI-parancssoron keresztül létrehozott entitások is mindig `owner_id=user.id`-t kapnak (`backend/routers/ai_router.py:40,51,68,84,96`), függetlenül attól, hogy az LLM mit adott vissza. A CSV-importtal automatikusan létrehozott cégek/kontaktok szintén az importáló userre kerülnek (`backend/routers/data_io.py:107,111-116`). A `TimeEntry.user_id` (a "ki loggolta" mező) ugyanígy mindig `user.id` (`backend/routers/projects.py:164`), sosem kliens input.

**Nincs a UI-ban semmilyen felület owner kézi kiválasztására/megváltoztatására** — ld. 10. szakasz.

---

## 4. Automatizmusok, ütemezett feladatok, értesítések

### Cron / scheduled task / worker / queue-consumer

**Egy sem található a kódbázisban.** A teljes `backend/` fában végzett keresés `APScheduler`, `BackgroundTasks`, `asyncio.sleep`, `while True`, `celery`/`Celery`, `cron`, `schedule.` mintákra **nulla találatot** adott. A `backend/requirements.txt` sem tartalmaz ütemező/queue csomagot (nincs `apscheduler`, `celery`, `rq`). Az egyetlen induláskor lefutó hook a `@app.on_event("startup")` (`backend/server.py:139-141`), ami csak a `seed()`-et hívja (táblák létrehozása + demo adatok) — ez nem ismétlődő job, csak egyszeri induláskori lépés.

### "N nap után történjen valami" / follow-up logika

Létezik, de **nem ütemezett job formájában**, hanem kérés-időben, lusta (lazy) számítással, minden egyes `GET /api/notifications` hívás alkalmával (`backend/routers/notifications.py:73-75` → `_sync()` → `_build_desired()`):

- **`auto_overdue`**: egy `Activity`, amit a user birtokol (`owner_id == user.id`), nincs kész (`completed == False`), és a `due_date` a mai nap előtt van (`notifications.py:18-33`).
- **`auto_due_today`**: ugyanaz, de a `due_date` == ma (`notifications.py:34-40`).
- **`auto_project_risk`**: egy `Project`, amit a user birtokol, nincs `completed`/`cancelled` állapotban, és vagy túllépte a becsült órakeretet (`logged_hours_for(...) > estimated_hours`) vagy elmúlt a `end_date`-je (`notifications.py:42-54`).

A `_sync()` (`notifications.py:58-70`) a "jelenleg kívánt" halmazt egy determinisztikus `key` mezővel (pl. `f"overdue:{activity_id}"`) veti össze a DB-ben meglévő `Notification` sorokkal: hozzáadja a hiányzókat, törli azokat az `auto_*` sorokat, amik már nem aktuálisak. **Fontos**: ez csak akkor fut le, ha a userhez tartozó munkamenet ténylegesen lekéri a `GET /api/notifications`-t (pl. a NotificationBell megnyitásakor/pollingjakor) — nincs olyan folyamat, ami session nélkül, a háttérben generálná ezeket bárkinek.

### Entitás-állapotváltozás → másik entitás létrehozása/módosítása (trigger)

**Nem található egyetlen ilyen trigger sem.** Konkrétan ellenőrizve:
- **Deal stage → "won"/"lost" → Project létrehozás**: nincs. A `update_stage` (`backend/routers/deals.py:73-83`) kizárólag a `Deal.stage` és `Deal.probability` mezőket módosítja, `Project`-et, `Activity`-t vagy `Notification`-t nem importál, nem hoz létre. (Strukturálisan is alátámasztva: nincs `Deal↔Project` FK a modellben, ld. 2. szakasz.)
- **Project status váltás → bármilyen mellékhatás**: nincs. `update_project` (`backend/routers/projects.py:117-127`) egy sima generikus `setattr` update, nincs utólagos hook.
- Amit *van* (de ez inkább adatkonzisztencia-cascade, nem üzleti trigger): entitás törlésekor a gyerek FK-k nullázása (`delete_company`: `companies.py:76-79`; `delete_contact`: `contacts.py:88-89`; `delete_deal`: `deals.py:93`), illetve `TimeEntry` sorok törlése projekt törlésekor (`projects.py:136-137`, DB CASCADE is ezt tenné amúgy is).
- **CSV import → Company automatikus létrehozása** ismeretlen cégnév esetén (`backend/routers/data_io.py:103-110`) — ez az egyetlen cross-entity "automatikus létrehozás" trigger a teljes kódbázisban, és kizárólag a kontakt-importra korlátozódik.

### Email / Slack / egyéb kimenő értesítés

**Nem található valódi kimenő email/Slack integráció sehol.** Az egyetlen "értesítés" jellegű funkció az in-app `Notification` tábla (ld. fent), amit a frontend `NotificationBell`/`NotificationContext` 60 másodpercenként pollingol (`frontend/src/context/NotificationContext.jsx:14-18`). A README-ben "Email logging" néven említett funkció (Iteration 3) a kódban ellenőrizve **nem valódi email küldés/fogadás**, hanem egy manuális napló-bejegyzés: a `ContactDetail.jsx` "Log email" modalja (`frontend/src/pages/ContactDetail.jsx:24-35`) egy sima `POST /api/activities` hívást indít `type: "email"`-lel és a tárgyba fűzött `[Inbound]`/`[Outbound]` prefixszel — ez egy manuálisan rögzített `Activity`, nincs mögötte tényleges levelezőrendszer-integráció (SMTP/IMAP/Gmail API).

### AI parancs-folyamat (`backend/ai_service.py` + `backend/routers/ai_router.py`)

1. `POST /api/ai/command` — `get_current_user` védi (bármely nem-vendég *és* vendég szerepkör is elérheti az LLM-válaszig; az írás van csak vendégnek tiltva, ld. lentebb) (`ai_router.py:103-105`).
2. API kulcs feloldás: `get_openrouter_key(db)` — előbb az `AppSetting` táblában tárolt, Fernet-titkosított `openrouter_api_key`-t próbálja (`ai_service.py:35-41`, dekódolás sikertelensége esetén `None`), majd `OPENROUTER_API_KEY` env változóra esik vissza (`ai_service.py:42`). Ha nincs kulcs: HTTP 400 (`ai_router.py:107-109`).
3. Modell feloldás: `AppSetting.openrouter_model` → `OPENROUTER_MODEL` env → hardcoded default `"deepseek/deepseek-chat-v3-0324:free"` (`ai_service.py:45-48`).
4. Kontextus: egy soros összegzés a Contact/Company/Deal/Project darabszámokról (`ai_router.py:19-24`), rendszerüzenetként hozzáfűzve.
5. Rendszerprompt (`ai_service.py:51-70`) szigorú JSON választ kér: `{"action", "data", "message"}`, ahol az `action` egyike `create_contact/create_company/create_deal/create_project/create_activity/summarize/answer/search`-nek, és a promptban explicit fel vannak sorolva a megengedett enum-értékek is.
6. HTTP hívás az OpenRouter chat completions végpontjára (`ai_service.py:73-120`), 60s timeout, `temperature=0.3`.
7. Válasz parse — ha a JSON parse elbukik, a nyers LLM-szöveg `{"action":"answer",...}`-ként kerül visszaadásra, hiba dobása helyett (`ai_service.py:112`).
8. **Szerver-oldali validáció írás előtt** (`_execute()`, `backend/routers/ai_router.py:27-100`) — teljesen független az LLM saját instrukcióitól: minden `create_*` akciónál az enum mezők (`status`, `stage`, `priority`, `type`) egy hardcoded `VALID_*` halmaz ellen vannak ellenőrizve, érvénytelen érték esetén egy alapértelmezettre esik vissza (pl. `"lead"`, `"planning"`, `"medium"`, `"task"`) — nem hibát dob. `owner_id` itt is mindig `user.id` (sosem az LLM adata).
9. Vendég (`guest`) szerepkör esetén write-akció HTTP 403-at kap, mielőtt `_execute` lefutna (`ai_router.py:121-126`) — ez a guard szerver oldalon, nem az LLM döntésén múlik.
10. Minden parancs naplózásra kerül `AICommandLog`-ba, akciótól függetlenül (`ai_router.py:128-130`).

---

## 5. Kommunikáció / kapcsolattartás nyomon követése

Egyetlen interakció-napló jellegű modell létezik: **`Activity`** (`backend/models.py:109-122`), amely egyszerre kapcsolódhat (nullable FK-kon keresztül) Contact, Company, Deal és Project entitásokhoz. Típusai: `call, email, meeting, task, note` (`schemas.py:9`). Nincs külön "Note" modell.

A `backend/routers/activities.py` CRUD-ot és egy `PATCH /{id}/toggle` (completed flip) végpontot ad, valamint szűrést `contact_id`/`deal_id`/`project_id`/`completed`/`upcoming` szerint (`activities.py:12-25`).

**"Utolsó kontakt dátuma" mező: nem található a kódban.** A `last_contact`/`lastContact` kulcsszavakra a teljes backend/frontend fában nulla találat van, és sehol nincs olyan lekérdezés, ami `MAX(Activity.created_at)`-ot számolna kontaktonként/cégenként.

**"Kinél van a labda" / várakozás-jelző: nem található a kódban.** Nincs `waiting`, `follow_up`, `next_action`, `waiting_on` jellegű mező vagy logika sehol.

Az "email logging" funkció (ld. 4. szakasz) egy manuálisan kitöltött `Activity` rekord `type="email"`-lel, `[Inbound]`/`[Outbound]` iránnyal a tárgyban (`frontend/src/pages/ContactDetail.jsx:17,24-35`) — nem automatikus/integrált levelezés-követés.

---

## 6. Mérföldkövek és számlázás

**Nincs Milestone/Phase modell sehol.** A `models.py` teljes átvizsgálása (164 sor) és kulcsszó-keresés (`milestone`, `phase`, `stage_history`) egyaránt nulla találatot adott a backendben és a frontendben is. A `Project` modellen csak egyetlen `status` mező van (5 fix érték), semmilyen szabadon szerkeszthető vagy fix-sablon fázis/mérföldkő-lista nincs implementálva — sem DB-táblaként, sem hardcoded konstansként (a `Deal.stage`-hez hasonló `STAGE_PROBABILITY` dict, `backend/routers/deals.py:10-11`, projektekre nincs megfelelője).

**Nincs Invoice/Payment/Bill modell sehol** a `models.py`-ban vagy a `schemas.py`-ban. A `invoice`/`payment`/`billing` kulcsszavakra a teljes kódbázisban nulla releváns találat (a "billable"/"billable_amount" szavak külön fogalmak, nem invoice/payment enumok).

A számlázás jelenleg kizárólag futásidőben, perzisztált invoice/payment entitás **nélkül** van kiszámolva:
- `backend/utils.py:6-9` — `logged_hours_for()`: egy projekt összes `TimeEntry.hours`-ának összege (billable-szűrés nélkül).
- `backend/routers/projects.py:88-98` — a projekt-detail végpont futásidőben számolja: `billable_amount = SUM(hours WHERE billable=True) * hourly_rate`.
- `backend/routers/reports.py:20-56` — az utilization riport userenként ugyanígy, futásidőben szorozza össze a `TimeEntry.hours * Project.hourly_rate`-et.

Az egyetlen "fizetési-státusz-szerű" mező a teljes kódbázisban a `TimeEntry.billable` (Boolean, `models.py:132`) — ez egy egyszerű "számlázható-e ez az időbejegyzés" jelző, **nem** invoice/payment-státusz enum (nincs `paid`/`unpaid`/`draft`/`sent`/`overdue` érték sehol). Nincs olyan modell, ami nyomon követné, hogy egy összeg ténylegesen ki lett-e számlázva vagy kifizetve.

---

## 7. Beajánlás / kapcsolati háló

**Nincs `referrer`/`source`/`referred_by` mező sem a Contact, sem a Company, sem a Deal modellen** (`backend/models.py:53-69,35-50,72-86` — a teljes mezőlista a 2. szakaszban). A `referrer`/`referral`/önálló `source` kulcsszavakra a backendben nulla releváns találat (az egyetlen "referrer"-szerű előfordulás a `rel="noreferrer"` HTML attribútum kimenő linkeken, `frontend/src/pages/Companies.jsx:70`, `CompanyDetail.jsx:32`, `Settings.jsx:71` — ez böngésző-biztonsági attribútum, nem CRM-mező).

Nincs önhivatkozó FK sehol (pl. nincs `Contact.referred_by_contact_id`), tehát a "melyik kontakt hány dealt hozott be" jellegű funkció **nem létezik** a kódban.

**Kapcsolattartó vs. fizető/szerződő fél megkülönböztetése: nem található.** A `Deal` és a `Project` is pontosan két kapcsolati mezőt hordoz: `company_id` és `contact_id` (`models.py:82-83`, `102-103`) — nincs külön `billing_company_id`/`billing_contact_id` mező, és mivel nincs Invoice modell sem (ld. 6. szakasz), invoice-szintű megkülönböztetés sem létezhet. Egy Deal/Project pontosan egy cég- és egy kontakt-párost hordoz, amit a kód egyszerre használ kapcsolat-jelölésre és (a futásidejű számítás alapjaként) számlázásra is.

---

## 8. Jogosultságok / szerepkörök

### Szerepkör-modell

`ROLE_LEVELS = {"guest": 0, "user": 1, "manager": 2, "admin": 3}` — szigorú, numerikus hierarchia (`backend/auth.py:12`). Két dependency védi a végpontokat:

- **`require_role(min_role)`** (`auth.py:85-90`): `ROLE_LEVELS[user.role] < ROLE_LEVELS[min_role]` esetén HTTP 403. Ismeretlen role `0` szintet kap.
- **`require_write`** (`auth.py:93-97`): kizárólag azt nézi, hogy `role == "guest"` — ha igen, HTTP 403 ("Guests have read-only access"); `user`/`manager`/`admin` mind átmegy. Ez **nem** a `ROLE_LEVELS`-t használja, hanem egy direkt guest-ellenőrzés.

Auth mechanizmus: bcrypt jelszó-hash → JWT (HS256) access (12 óra) + refresh (7 nap) token, httpOnly cookie-ban (`SameSite=Lax`, `Secure` env-vezérelt `COOKIE_SECURE`-rel) vagy `Authorization: Bearer` headerben (`auth.py:29-64`, cookie elsőbbséget élvez a headerrel szemben). A deaktivált (`active=False`) userek minden kérésnél elutasításra kerülnek (`auth.py:76-77`), nem csak új loginnál.

### Ki mit láthat

- **Admin-only**: user-kezelés (`/api/users` összes végpontja), Settings (`/api/settings`, OpenRouter kulcs) — mindkettő `require_role("admin")` (`backend/routers/users.py:14,20,35,60`, `backend/routers/settings_router.py:13,23`).
- **Manager+ (manager vagy admin)**: utilization riport (`GET /api/reports/utilization`, `require_role("manager")` — `backend/routers/reports.py:22`), ami az összes user óra- és pénzösszegét mutatja (nem csak sajátját).
- **Bármely bejelentkezett user (guest is)**: az összes olvasó (`GET`) végpont Company/Contact/Deal/Project/Activity/Dashboard-on, beleértve a `Deal.value`/`Project.budget`/`Project.hourly_rate` mezőket is — **nincs ár/pénzügyi adat elrejtve szerepkör szerint** az alap CRUD listákon/detail nézeteken (nem található semmilyen mezőszintű RBAC-szűrés a `*Out` sémákban).
- **Írás (Create/Update/Delete)**: `require_write` — mindenki, aki nem `guest`. A vendég tehát mindent lát (árakat, fizetési/óradíj-adatokat is), csak nem írhat.
- **CSV export/import** (`data_io.py`): csak `get_current_user`/`require_write`, **nincs `require_role`** — bármely nem-vendég user tömegesen exportálhatja az összes CRM-adatot CSV-ben, admin-szint nélkül. *(Nem egyértelmű a kódból, hogy ez szándékos-e — a kódban nincs erre utaló kommentár.)*
- **AI parancssor**: bármely bejelentkezett user (guest is) kaphat LLM-választ; írási akció guestnek szerver oldalon tiltva (`ai_router.py:121-126`).

---

## 9. API felület

Minden végpont `/api` prefix alatt, `backend/server.py:33-45` regisztrálja a routereket ebben a sorrendben. Ezen kívül: `GET /api/health` (`server.py:48-50`, nincs auth).

### `/api/auth` — `backend/routers/auth_router.py`

| Metódus | Path | Cél | Védelem |
|---|---|---|---|
| POST | `/register` | Regisztráció (csak ha `ALLOW_REGISTRATION=true`) | nincs (rate limit: 3/perc) |
| POST | `/login` | Bejelentkezés, cookie-k beállítása | nincs (rate limit: 5/perc) |
| POST | `/logout` | Cookie-k törlése | nincs |
| GET | `/me` | Aktuális user lekérdezése | `get_current_user` |
| POST | `/refresh` | Token frissítés refresh cookie-ból | nincs (rate limit: 10/perc) |

### `/api/users` — `backend/routers/users.py`

| Metódus | Path | Cél | Védelem |
|---|---|---|---|
| GET | `/` | Userek listázása | `require_role("admin")` |
| POST | `/` | User létrehozása (role is megadható) | `require_role("admin")` |
| PUT | `/{user_id}` | Update (name/role/locale/active/password) | `require_role("admin")` |
| DELETE | `/{user_id}` | Törlés | `require_role("admin")` |
| PUT | `/me/locale` | Saját nyelv beállítása | `get_current_user` |

### `/api/companies` — `backend/routers/companies.py`

| Metódus | Path | Cél | Védelem |
|---|---|---|---|
| GET | `/` | Lista/keresés | `get_current_user` |
| GET | `/{id}/detail` | Cég + kapcsolódó kontaktok/dealek/projektek | `get_current_user` |
| GET | `/{id}` | Egy cég | `get_current_user` |
| POST | `/` | Létrehozás | `require_write` |
| PUT | `/{id}` | Módosítás | `require_write` |
| DELETE | `/{id}` | Törlés + gyerek FK-k nullázása | `require_write` |

### `/api/contacts` — `backend/routers/contacts.py`

| Metódus | Path | Cél | Védelem |
|---|---|---|---|
| GET | `/` | Lista/keresés/szűrés | `get_current_user` |
| GET | `/{id}/detail` | Kontakt + dealek/aktivitások | `get_current_user` |
| GET | `/{id}` | Egy kontakt | `get_current_user` |
| POST | `/` | Létrehozás | `require_write` |
| PUT | `/{id}` | Módosítás | `require_write` |
| DELETE | `/{id}` | Törlés + gyerek FK-k nullázása | `require_write` |

### `/api/deals` — `backend/routers/deals.py`

| Metódus | Path | Cél | Védelem |
|---|---|---|---|
| GET | `/` | Lista, `stage` szűréssel | `get_current_user` |
| GET | `/{id}/detail` | Deal + cég/kontakt/aktivitások | `get_current_user` |
| GET | `/{id}` | Egy deal | `get_current_user` |
| POST | `/` | Létrehozás | `require_write` |
| PUT | `/{id}` | Teljes módosítás | `require_write` |
| PATCH | `/{id}/stage` | Csak stádium váltás (valószínűség újraszámolása) | `require_write` |
| DELETE | `/{id}` | Törlés + aktivitások nullázása | `require_write` |

### `/api/projects` — `backend/routers/projects.py`

| Metódus | Path | Cél | Védelem |
|---|---|---|---|
| GET | `/` | Lista (lapozott, `X-Total-Count` header) | `get_current_user` |
| GET | `/{id}` | Egy projekt (számolt `health`/`logged_hours`) | `get_current_user` |
| GET | `/{id}/detail` | Projekt + időbejegyzések + aktivitások | `get_current_user` |
| POST | `/` | Létrehozás | `require_write` |
| PUT | `/{id}` | Módosítás | `require_write` |
| DELETE | `/{id}` | Törlés + időbejegyzések törlése | `require_write` |
| GET | `/{id}/time` | Időbejegyzések listája | `get_current_user` |
| POST | `/{id}/time` | Időbejegyzés rögzítése | `require_write` |
| DELETE | `/{id}/time/{entry_id}` | Időbejegyzés törlése (saját, vagy admin/manager) | `require_write` + tulajdon-ellenőrzés |

### `/api/activities` — `backend/routers/activities.py`

| Metódus | Path | Cél | Védelem |
|---|---|---|---|
| GET | `/` | Lista/szűrés (`contact_id`/`deal_id`/`project_id`/`completed`/`upcoming`) | `get_current_user` |
| POST | `/` | Létrehozás | `require_write` |
| PUT | `/{id}` | Teljes módosítás | `require_write` |
| PATCH | `/{id}/toggle` | `completed` flip | `require_write` |
| DELETE | `/{id}` | Törlés | `require_write` |

### `/api/dashboard` — `backend/routers/dashboard.py`

| Metódus | Path | Cél | Védelem |
|---|---|---|---|
| GET | `/stats` | KPI-k és chart-adatok | `get_current_user` |

### `/api/ai` — `backend/routers/ai_router.py`

| Metódus | Path | Cél | Védelem |
|---|---|---|---|
| POST | `/command` | Szabadszöveges parancs → OpenRouter → opcionális rekord-létrehozás | `get_current_user` (írás guestnek tiltva) |
| GET | `/history` | Saját utolsó 20 AI-parancs naplója | `get_current_user` |

### `/api/settings` — `backend/routers/settings_router.py`

| Metódus | Path | Cél | Védelem |
|---|---|---|---|
| GET | `/` | OpenRouter kulcs (van-e beállítva) + modell lekérdezése | `require_role("admin")` |
| PUT | `/` | OpenRouter kulcs (Fernet-titkosítva) / modell beállítása | `require_role("admin")` |

### Data I/O — `backend/routers/data_io.py` (prefix `/api`)

| Metódus | Path | Cél | Védelem |
|---|---|---|---|
| GET | `/export/contacts.csv` | Kontaktok CSV exportja | `get_current_user` |
| GET | `/export/companies.csv` | Cégek CSV exportja | `get_current_user` |
| GET | `/export/deals.csv` | Dealek CSV exportja | `get_current_user` |
| GET | `/export/projects.csv` | Projektek CSV exportja | `get_current_user` |
| POST | `/import/contacts` | Kontaktok CSV importja (ismeretlen cégnév → auto cég-létrehozás, duplikált email kihagyva) | `require_write` |

### `/api/reports` — `backend/routers/reports.py`

| Metódus | Path | Cél | Védelem |
|---|---|---|---|
| GET | `/utilization` | Userenkénti óra/összeg/kihasználtság % (hét vagy hónap) | `require_role("manager")` |

### `/api/notifications` — `backend/routers/notifications.py`

| Metódus | Path | Cél | Védelem |
|---|---|---|---|
| GET | `/` | Auto-értesítések szinkronizálása + listázás (olvasatlan elöl) | `get_current_user` |
| POST | `/{id}/read` | Egy értesítés olvasottá jelölése | `get_current_user` |
| POST | `/read-all` | Összes olvasatlan olvasottá jelölése | `get_current_user` |

---

## 10. UI / felhasználói folyamatok

### Route-térkép (`frontend/src/App.js`)

| Path | Komponens | Korlátozás |
|---|---|---|
| `/login` | `Login` | nyilvános |
| `/` | `Dashboard` | bármely bejelentkezett user |
| `/contacts`, `/contacts/:id` | `Contacts`, `ContactDetail` | bármely bejelentkezett user |
| `/companies`, `/companies/:id` | `Companies`, `CompanyDetail` | bármely bejelentkezett user |
| `/deals`, `/deals/:id` | `Deals`, `DealDetail` | bármely bejelentkezett user |
| `/projects`, `/projects/:id` | `Projects`, `ProjectDetail` | bármely bejelentkezett user |
| `/activities` | `Activities` | bármely bejelentkezett user |
| `/calendar` | `Calendar` | bármely bejelentkezett user |
| `/utilization` | `Utilization` | `roles={["admin","manager"]}` |
| `/users` | `Users` | `adminOnly` |
| `/settings` | `Settings` | `adminOnly` |

A "bármely bejelentkezett user" nézeteken belül a **guest** komponens-szinten (nem route-szinten) csak olvasásra van korlátozva (`can.write(user)`, `frontend/src/auth.jsx:49-52`) — az írás-gombok (create/edit/delete, kanban drag) rejtve/letiltva vannak számára, de a route maga elérhető.

### Fő képernyők entitásonként

| Entitás | Lista nézet | Kanban/board | Detail nézet | Create/Edit |
|---|---|---|---|---|
| Company | kártyarács, kereséssel | nincs | csak olvasható összegzés + kapcsolódó rekordok | modal a lista oldalon |
| Contact | sorlista, kereséssel + státusz-szűrővel, CSV export/import gombokkal | nincs | overzió + dealek + aktivitás-idővonal + "Log email" | modal a lista oldalon |
| Deal | lista **és** kanban (váltható), `@hello-pangea/dnd` | **igen** — oszlop stádiumonként, drag-and-drop stage-váltással | csak olvasható + idővonal | modal (title/value/stage/company/contact/notes — `probability` és `expected_close` **nincs** a formban) |
| Project | kártyarács, státusz-szűrővel, lapozással | nincs | Idő&Ráfordítás panel (logged/estimated/remaining/billable), időbejegyzés CRUD, idővonal | modal (name/description/status/priority/budget/company/estimated_hours/hourly_rate — `start_date`/`end_date` **nincs** a formban) |
| Activity | sorlista, kész/nincs-kész szűrővel, inline toggle | nincs | nincs önálló oldal (csak beágyazva más entitások idővonalán + Calendar) | modal a lista oldalon |
| User | sorlista (csak admin route) | nincs | nincs | modal (email csak létrehozáskor szerkeszthető) |
| Notification | nincs önálló oldal, csak harang-dropdown | — | — | — |

### UI–backend lefedettség (mi van ténylegesen bekötve, mi csak backend-ben létezik)

- **Deal stage váltás**: dropdown a create/edit modalban **és** kanban drag — mindkettő a `PATCH /deals/{id}/stage` (drag esetén) vagy a `PUT` (form esetén) végpontot hívja (`frontend/src/pages/Deals.jsx:49-58,150-154`). Szabad szöveges bevitel nincs.
- **`Deal.probability`, `Deal.expected_close`**: megjelennek olvasható nézetekben (kártya, lista, detail), de **nincsenek a create/edit formban** — a UI-ból gyakorlatilag csak olvashatók/backend-vezéreltek.
- **Project status**: csak dropdown a modalban, kanban/drag **nincs** a projekteknél (a Deals-szel ellentétben).
- **Project `health`** (`on_track`/`at_risk`/`over_budget`/stb.): csak megjelenített badge, nincs hozzá form-mező — tisztán számolt, csak-olvasható érték.
- **TimeEntry logolás**: bekötve, kizárólag a `ProjectDetail.jsx`-en ("Log time" gomb → modal → `POST /projects/{id}/time`); nincs másik belépési pont (nem érhető el pl. az Activities oldalról).
- **Notifications**: harang-ikon minden védett oldalon (a `Layout`-ba ágyazva), dropdown lista, egyenkénti és "összes" olvasottá jelölés; `NotificationContext` 60 mp-enként pollingol. **Nincs önálló `/notifications` route/oldal.**
- **AI parancssor**: **kizárólag a Dashboard oldalra van bekötve** (`frontend/src/pages/Dashboard.jsx:11,65`) — nem globálisan elérhető a Layoutból, más oldalakról nem használható.
- **Riportok**: Dashboard (KPI csempék + pipeline-by-stage oszlopdiagram + contacts-by-status kördiagram + upcoming tasks), Utilization (admin/manager, heti/havi bontás, oszlopdiagram + táblázat). Nincs más riport-oldal (pl. nincs projekt-profitabilitás riport, nincs "Reports" nav-elem külön a kettőn kívül).
- **CSV import/export**: a backend mind a 4 entitásra (contacts/companies/deals/projects) exportot kínál, de **a frontend csak a kontaktok export/importját köti be** (`frontend/src/pages/Contacts.jsx:54-72,79-82`). A cégek/dealek/projektek exportja backend-only, a UI-ból nem elérhető; import ezekre a típusokra a backendben sincs implementálva.
- **Settings oldal**: OpenRouter API kulcs + modell-választó (4 hardcoded modell) — funkcionális. Google Workspace kártya csak megjelenítés, statikus "Not connected" badge, **nincs valódi OAuth-folyamat** sem a Settingsben, sem a Login oldal Google-gombja mögött (az csak egy hibaüzenetet mutat: "Google Workspace login requires Google Cloud credentials...", `frontend/src/pages/Login.jsx:119`).
- **User-kezelés**: teljes admin UI (`Users.jsx`) — létrehozás, szerepkör-váltás, aktív/inaktív, törlés (önmagát nem törölheti).
- **`owner_id`**: a backend séma tartalmazza minden fő entitáson, de **a frontend egyetlen formján sincs owner-mező** (sem szerkeszthető, sem csak-olvasható megjelenítésként) — ez a mező kizárólag a backendben létezik, UI belépési pont nélkül.
- **Referrer/source mező**: sem a backend sémában, sem a frontend formokon nem található (ld. 7. szakasz is).
- **i18n**: `i18n.js` EN és HU blokkja kulcsról kulcsra megegyező struktúrájú, mindkét nyelv ténylegesen be van kötve (nem csak csonk).

---

## 11. Ismert hiányosságok, TODO-k, dead code

### TODO / FIXME / HACK / stb.

A teljes `backend/` és `frontend/src/` fában (case-insensitive) **nulla találat** az alábbiakra: `TODO`, `FIXME`, `HACK`, `XXX`, "not implemented", "unused", "deprecated", "dead code". A kódbázis nem tartalmaz ilyen jelölésű kommentet.

### Gyanúsan holt (nem használt) mezők

- **`User.avatar_url`** (`backend/models.py:26`, séma: `schemas.py:30`) — sehol nincs beállítva vagy kiolvasva a routerekben vagy a frontendben. **Holt mező.**
- **`User.google_connected`** (`models.py:29`) és **`User.google_email`** (`models.py:30`) — sehol nincs írva/olvasva a saját definíciójukon kívül. **Holt mezők.**
- **`User.auth_provider`** (`models.py:28`) — mindig `"local"`-ra van írva (`backend/routers/auth_router.py:34`, `users.py:26`, `server.py:67,81`), de sosem van kiolvasva/elágaztatva (nincs `if user.auth_provider == "google"` logika sehol). Write-only mező.
- Ezek a mezők egy nem megvalósított Google Workspace OAuth funkcióhoz tartoznak — a README ezt explicit "Backlog"-ként jelöli (`README.md:37-39`), és a Settings/Login oldalak UI-ja is csak dekoratív erre nézve (ld. 10. szakasz).
- **Ellenőrizve, hogy NEM holtak**: `Project.estimated_hours` és `Project.hourly_rate` (az `ALTER TABLE`-lel utólag hozzáadott oszlopok, ld. 2. szakasz) — mindkettő aktívan használt (`projects.py`, `notifications.py`, `data_io.py`, `ProjectDetail.jsx`, `Projects.jsx`).

### Árva frontend fájlok

**Nincs.** Mind a 15 `pages/` fájl és mind a 4 `components/` fájl be van kötve/route-olva az `App.js`-ben vagy importálva máshonnan.

### `data_io.py` bekötöttsége

Ld. 10. szakasz — csak a kontakt export/import van bekötve a UI-ba; a cégek/dealek/projektek export-végpontjai backend-only, a UI-ból el nem érhető "holt" funkciók (import ezekre nincs is implementálva backend oldalon).

---

## Nem egyértelmű pontok

Az alábbiakat a kód alapján nem lehetett egyértelműen eldönteni — emberi visszaigazolás javasolt:

1. **`Notification.type = "info"` alapértelmezett érték célja** (`backend/models.py:142`) — a kódban egyetlen endpoint sem hoz létre `"info"` típusú értesítést, csak a 3 `auto_*` típust. Nem egyértelmű a kódból, hogy ez egy meg nem valósított "manuális/rendszer-értesítés" funkció maradványa, vagy csak egy oszlop-default, aminek nincs ténylegesen felhasznált ága.
2. **CSV export/import (`data_io.py`) jogosultsági szintje** — csak `get_current_user`/`require_write` védi, nincs `require_role`, tehát bármely nem-vendég user tömegesen exportálhatja az összes adatot. Nem egyértelmű a kódból, hogy ez szándékos tervezési döntés (nincs hozzá magyarázó kommentár).
3. **`Project.priority` és `User.role` mezők hiányzó Pydantic `Literal` típusa** — a `CLAUDE.md` szerint minden enum-mezőnek `Literal` típust kellene kapnia a `schemas.py`-ban, de ezen a kettőn csak router-szintű `VALID_*` halmaz-ellenőrzés van, nem Pydantic-szintű. Nem egyértelmű, hogy ez tudatos kivétel-e, vagy technikai adósság.
4. **`TimeEntry` törlési jogosultság-ellenőrzés mintája** (`backend/routers/projects.py:185-186`: `user.role not in ("admin","manager")`) — ez egy hardcoded tuple-ellenőrzés, eltér a többi helyen használt `ROLE_LEVELS`/`require_role` mintától. Nem egyértelmű, hogy ez szándékos vagy inkonzisztencia.
5. **`JWT_SECRET`/`FERNET_KEY` tényleges production-beli provisioning módja** — a kódból csak annyi látszik, hogy `os.environ[...]`-ból kötelezően olvasandók (`backend/auth.py:25-26`, `backend/ai_service.py:10`), a tényleges kulcskezelési folyamat (pl. secrets manager) a kódon kívül esik.
6. **Az AI parancssor pontos, ténylegesen támogatott parancs-grammatikája** a felhasználó szemszögéből — a rendszerprompt (`ai_service.py:51-70`) meghatározza az elfogadott `action`-öket, de hogy az LLM ebből mennyire megbízhatóan ismer fel egy adott szabadszöveges magyar/angol mondatot, az modellfüggő, kódból nem verifikálható.
7. **Notification `link` mező generálásának teljessége** — jelenleg csak a 3 auto-típusnál van kitöltve (`/activities`, `/projects/{id}`), de ez működési kérdés, nem funkcionalitás-hiány; jelezve csak a teljesség kedvéért.

---

*Riport készült: teljeskörű, csak-olvasás jellegű kódvizsgálattal, 5 párhuzamos kutató-ágens + saját közvetlen fájl-olvasás és kereszt-ellenőrzés (self-review) alapján. Minden megállapítás forrás-hivatkozással (`fájl:sor`) alátámasztva a fenti szakaszokban.*
