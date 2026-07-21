# wespeak.ai CRM — Integrációs terv (új igények → jelenlegi MVP)

> Ez a dokumentum a megbeszélt kliens-életciklus igényeket veti össze a `DISCOVERY_REPORT.md`-ben leltárazott jelenlegi MVP-vel, és fázisokra bontott, konkrét implementációs tervet ad. Claude Code-nak közvetlenül átadható: minden változás a tényleges fájlokra (`backend/models.py`, `backend/schemas.py`, `backend/routers/*`, `frontend/src/*`) hivatkozik.
>
> **Stack** (a report szerint): FastAPI + SQLAlchemy 2.0 + Pydantic v2, PostgreSQL, React 18 (CRA, JS), Docker Compose. Az adatbázis jelenleg **üres** — tiszta lappal tervezünk, nincs backfill.
>
> **Audit átvezetve** (v2): a terv átment egy független auditon (ld. `AUDIT_FINDINGS.md`). A 4 blokkoló és a javítandók be vannak építve; a döntéseket a „Rögzített döntések" szakasz tartalmazza.

---

## 0. Vezetői összefoglaló — mi van, mi hiányzik

| Megbeszélt igény | Jelenlegi állapot az MVP-ben | Teendő |
|---|---|---|
| Konfigurálható hozzáférés-kezelés (admin állítja, ki mit lát/tehet; deal/projekt public v. invite-only) | Fix `ROLE_LEVELS` (admin/manager/user/guest); **minden bejelentkezett user lát minden árat**; nincs objektum-szintű láthatóság, nincs meghívás | **Új** (jelentős bővítés) |
| Lead claim (közös inbox, felelős, elakadás-figyelmeztetés) | `owner_id` az 5 fő CRM-entitáson (Company/Contact/Deal/Project/Activity), de mindig a létrehozóra áll, UI-ból nem állítható | **Bővítés** |
| Kommunikációs napló + irány | `Activity` modell megvan (call/email/meeting/task/note), email-log `[Inbound]/[Outbound]` prefixszel a tárgyban | **Bővítés** |
| Labda-státusz (kinél pattog) | **Nincs** — se `last_contact`, se irány-mező, se „várakozás" jelző | **Új** |
| Küszöb-emlékeztető (X nap után) | Van lusta, kérés-idejű értesítés, de nincs follow-up / „válaszra vár" típus | **Bővítés** |
| Esemény-napló + életút-nézet + aggregált analitika + státusz-visszalépés naplózása | **Nincs** — a `PATCH /stage` felülírja a stádiumot history nélkül; nincs audit-napló sehol | **Új** |
| Lead-típus (egy-/kétoldalú) + szerződő fél elkülönítése | **Nincs** — egy `company_id`+`contact_id` pár szolgál kapcsolatra és számlázásra is | **Új** |
| Beajánló követése | **Nincs** referrer mező, nincs önhivatkozó kapcsolat, nincs rollup (`tags` JSONB viszont van) | **Új** |
| Deal „won" → Projekt automatikus létrehozás | **Nincs** — se Deal↔Project FK, se trigger | **Új** |
| Mérföldkövek + rugalmas számlázás (HUF/EUR, külön munka- és fizetési státusz, visszafordítható) | **Nincs** Milestone/Invoice modell; csak `TimeEntry.billable` bool; pénznem alap EUR | **Új** |
| Utókövetés (lezárás + N nap → task) | **Nincs** — és **nincs semmilyen ütemező/háttérfolyamat** | **Új + architekturális bővítés** |
| AI-native / MCP szerver (AI is tudja kezelni a rendszert) | **Részben** — FastAPI/OpenAPI + tipizált Pydantic + meglévő LLM-minta (`ai_service.py`) kedvező, de nincs gép-hitelesítés, gazdag query, esemény-kivezetés; és nincs MCP szerver | **Új + enablerek a többi fázisban** |

### Rögzített döntések (ebből a beszélgetésből)

- **Hozzáférés**: admin szabadon konfigurálhatja, ki mit tehet. Minden deal/projekt `public` vagy `invite-only`. Admin és manager alapból mindent lát. User/guest láthatósága (pénz is) konfigurálható és meghívás-alapú. → réteges modell, ld. lentebb.
- **Pénznem**: HUF és EUR is támogatott, rekordonként.
- **Számlázhatóság külön a munka-státusztól**: egy mérföldkő „teljesítve" jelentheti azt is, hogy a kliens elfogadására várunk — a fizetési státusz ettől független.
- **Visszalépés engedélyezett**: bármely státusz visszaléptethető, de **minden státuszváltás (előre és vissza is) naplózódik** az esemény-naplóba.
- **Stádium-guard**: most **nem** kell (szabad átmenetek), de később bevezethető — a mezőket úgy tervezzük, hogy ne zárja ki.
- **Owner-kötelezőség** (audit BL-4): a lead a közös inboxban maradhat owner nélkül, de **nem léphet `qualified` fölé claim (owner) nélkül**, és **projekt-létrehozáshoz owner kötelező**. Ez a védőháló a „ne süllyedjen el egy lead" ellen.
- **Pénzügyi maszkolás módja** (audit BL-3): az „A" minta — a pénz-mezők `Optional`-ek a `*Out` sémákban, és egy közös serializer-dependency null-ozza őket jogosultság híján (egy séma, egy helyen a logika).
- **Időkövetés szerepe** (audit JV-1): fix-áras modellben az órák/`billable`/utilization **belső költség- és kihasználtság-mérésre** maradnak (mennyi munka ment a fix árba) — a kliens felé a mérföldkövek számláznak, nem az óradíj.
- **„Passz" definíció** (audit JV-3): egy oda-vissza passz = a `ball_in_court` irányváltása (nálunk↔kliens). Az analitika ezt számolja.
- **Tesztelés**: egy lépés csak akkor kész, ha **minden teszt zöld**. Ez a „definition of done".
- **Commit**: minden fázist implementálunk, de fázisonként / funkciónként külön commit vagy PR.
- **Backup**: kell egy megoldás (ld. ops szakasz).
- **AI-native / MCP**: fontos, hogy az AI is tudja kezelni a rendszert. A cél: MCP szerver a CRM fölé, ami tool-ként kinyitja a műveleteket egy AI-ügynöknek. Az összes fázis tartsa be az AI-native elveket (ld. lentebb), és egy dedikált záró fázis építi meg magát az MCP szervert.

### Munkamódszer

- **Definition of done**: minden funkció akkor kész, ha a hozzá tartozó pytest integrációs tesztek (a meglévő élő-szerver minta szerint, `backend/tests/`) zölden futnak. Új funkció = új teszt.
- **Commit-stratégia**: fázisonként külön ág, azon belül funkciónként külön commit/PR (pl. „Fázis 1: capability mátrix backend", „Fázis 1: objektum-láthatóság szűrés", „Fázis 1: pénzügyi mező-maszkolás"). Így minden lépés külön review-zható és visszagörgethető.
- **Iteratív átadás**: fázisonként leszállítjuk és éles adaton kipróbáljátok, mielőtt a következőbe kezdünk.

### Architekturális megjegyzés: nincs ütemező

A report szerint **nulla** cron/scheduler/worker a kódban; minden időalapú logika lustán, `GET /api/notifications`-kor fut (`notifications.py:73-75`). Ez nem tud lefutni, ha az érintett user nem nyitja meg az appot, és nem tud „senkihez sem kötött" időalapú műveletet végezni. Ezért a valódi időalapú automatizmust (utókövetés, kihűlőben) egy napi háttérjobra (APScheduler) tesszük — az **utolsó fázisban**. Addig az 1–4. fázis a meglévő lusta mintával, ütemező nélkül is szállítható.

### Tervezési elv: moduláris, bővíthető adatstruktúra

Ahol egy minta több entitáson ismétlődik, ott általánosítunk: generikus `EventLog` (`entity_type`+`entity_id`), újrahasználható objektum-láthatóság/membership, közös capability-ellenőrzés, egységes owner/claim logika. **Amitől óvakodunk (túl-általánosítás):** teljesen konfigurálható „custom mezők" (EAV) réteg, általános workflow-motor, mindent egyetlen polimorf táblába gyömöszölő absztrakció — ezek 6 fős csapatnál ritkán térülnek meg. A cél „bővíthető", nem „mindent paraméterezhető".

### Tervezési elv: AI-native (MCP-készség)

A rendszert úgy építjük, hogy egy AI-ügynök (MCP szerveren keresztül) ugyanolyan biztonságosan és teljeskörűen tudja kezelni, mint egy ember. Ezt nem egy külön modul adja, hanem az egész API-n átvitt fegyelem:

- **Minden művelet API-n keresztül** — nincs olyan üzleti logika, ami csak a frontendben él. Ha a UI meg tud csinálni valamit, arra van tiszta végpont is. (A jelenlegi kód nagyrészt ilyen; a pár frontend-only logikát, pl. a `[Inbound]/[Outbound]` prefixet, kiváltjuk — ld. 0.2.)
- **Gépi olvasható, pontos séma** — FastAPI OpenAPI-ja már adott; kiegészítjük: `Literal` minden enum-mezőn (a report által jelzett `priority`/`role` hiány javítása), értelmes `summary`/`description` minden végponton (ebből lesznek az MCP tool-leírások), és egységes, strukturált hibaválaszok.
- **Ügynök mint principal** — az AI nem „belép userként", hanem saját, szűkített jogú identitása van, ugyanabba a capability-modellbe kötve (service-account / API-kulcs, ld. Fázis 1). A pénzügyi maszkolás és objektum-láthatóság rá is érvényes.
- **Gazdag olvasás/lekérdezés** — az ügynöknek jól kell tudnia kérdezni, nem csak írni: konzisztens szűrés, lapozás, és kereső-végpontok.
- **Kivezetett események** — a generikus `EventLog` (Fázis 0) adja az alapot ahhoz, hogy az ügynök lássa/követhesse a változásokat (később webhook/stream is építhető rá).

### Migrációs stratégia

Mivel az adatbázis üres, **Alembic** bevezetése a 0. fázisban a legolcsóbb: egy tiszta baseline a teljes (bővített) sémáról, innentől verziózott migrációk. Nincs régi adat, amit menekíteni kellene.

---

## Hozzáférés-kezelési modell (konceptuális)

Ez a rész magát a modellt írja le; a megvalósítás a Fázis 1-ben van. Négy réteg, egymásra épülve.

### 1. réteg — Szerepkörök (megmarad, jelentése tisztázva)

A meglévő `admin / manager / user / guest` marad, mint alap-besorolás:

- **admin** — teljes hozzáférés; ő konfigurálja a jogosultságokat és kezeli a usereket. (Fix, nem elvehető képességek: user-kezelés, jogosultság-konfigurálás.)
- **manager** — alapból **mindent lát** (minden deal/projekt, pénzügyek, riportok), teljes írás.
- **user** — normál tag; a `public` objektumokat és azokat látja, amikbe meghívták; a pénzügyi láthatósága konfigurálható.
- **guest** — legszűkebb; alapból csak olvasás, pénzügyek alapból rejtve; minden konfigurálható.

### 2. réteg — Objektum-láthatóság (új)

Minden `Deal` és `Project` kap egy `visibility` mezőt: `public` vagy `private` (invite-only).

- `public` — minden bejelentkezett user látja (a pénzügyi mezők a 4. réteg szerint maszkolva).
- `private` — csak a **tagok** (3. réteg) + admin + manager látják.
- A szervezeti alapértelmezés **`public`** (D5), amit az admin egy globális beállításban módosíthat.

### 3. réteg — Tagság / meghívás (új)

Generikus `EntityMembership` tábla (moduláris elv): `entity_type`, `entity_id`, `user_id`, `added_by`, `added_at`. A tulajdonos automatikusan tag. `private` objektumhoz csak tag (vagy admin/manager) fér hozzá. Meghívni az tud, akinek van rá képessége (4. réteg, `invite_members`).

### 4. réteg — Képességek (capabilities), admin által konfigurálható (új)

Egy **bounded** (véges, előre definiált) képesség-halmaz, amit az admin szerepkörönként ki/be kapcsolhat. Nem szabad-formátumú policy-motor — véges lista, hogy érthető és karbantartható maradjon:

| Képesség | Mit enged | Alap: admin | manager | user | guest |
|---|---|---|---|---|---|
| `view_financials` | Pénzügyi mezők látása (deal value, budget, óradíj, mérföldkő-összeg, pénz-riportok) | ✅ | ✅ | ⚙️ (alap: be) | ⚙️ (alap: ki) |
| `manage_deals` | Deal létrehozás/módosítás/törlés | ✅ | ✅ | ✅ | ❌ |
| `manage_projects` | Projekt + mérföldkő írás | ✅ | ✅ | ✅ | ❌ |
| `invite_members` | Tag hozzáadása private objektumhoz | ✅ | ✅ | ⚙️ (alap: be) | ❌ |
| `set_visibility` | Objektum public/private állítása | ✅ | ✅ | ⚙️ | ❌ |
| `reassign_owner` | Felelős átállítása máshoz | ✅ | ✅ | ⚙️ (alap: ki) | ❌ |
| `view_all_reports` | Összesített (nem csak saját) riportok | ✅ | ✅ | ⚙️ | ❌ |

⚙️ = admin által állítható; ✅/❌ = alap, de a nem-fix sorok szintén állíthatók. Fix (soha nem elvehető): `manage_users` és `configure_permissions` → csak admin.

**Tárolás**: a képesség-mátrix a meglévő `AppSetting` kulcs-érték táblában (`models.py:150-153`), pl. `role_capabilities` kulcs alatt JSON-ként — nem kell új tábla, és a kódban van beégetett alapérték fallback-nek.

**Kikényszerítés**: egy új `require_capability("x")` dependency (`auth.py`), a jelenlegi `require_role`/`require_write` mintára (`auth.py:85-97`), ami a userr szerepköréhez a konfigurált mátrixból nézi a jogot.

**Pénzügyi mező-maszkolás** (audit BL-3 → „A" minta): a pénz-mezők (`value`, `budget`, `hourly_rate`, mérföldkő-`amount`) `Optional`-ek a `*Out` Pydantic sémákban, és egy **közös serializer-dependency** null-ozza őket, ha a usernek/principálnak nincs `view_financials` joga — nem csak a UI-ban rejtve, hanem a backend válaszban is. Mivel a `response_model` route-szinten fix, a per-user rejtést a dependency végzi (egy séma, egy helyen a logika). A séma-alapon nem érintett felületeket külön kell kezelni: a `dashboard.py` KPI-k és a `data_io.py` CSV-export **nem** `*Out`-alapú, ezért ezekre a maszkolást explicit rá kell húzni. Az OpenAPI-ban (és így az MCP tool-sémákban) a mezők `Optional`-ként jelennek meg, a leírásukban jelezve, hogy jelenlétük jogosultságfüggő.

**Láthatóság-szűrés** (audit BL-2): egy közös helper (`backend/utils.py`) ad egy szűrő-feltételt — admin/manager → minden; egyébként `visibility='public' OR EXISTS(membership)`. Ezt **minden** olyan olvasó útra rá kell tenni, ami deal/projekt adatot ad vissza, nem csak a fő listákra:
- `deals.py`, `projects.py` lista + detail;
- `GET /companies/{id}/detail` és `GET /contacts/{id}/detail` (ezek kapcsolódó dealeket/projekteket adnak — report §9);
- `dashboard.py` (aggregátumok);
- `data_io.py` CSV-export (`/export/deals.csv`, `/export/projects.csv`) — erre **capability/role-gate is** kell, mert ma bármely nem-guest role-gate nélkül exportálhat mindent (report §8).

---

## Fázis 0 — Alapok (enablerek)

### 0.1 Migrációs alap (audit BL-1)
`alembic init`, egyetlen tiszta baseline a bővített sémáról, a `create_all` kiváltása (`server.py:54`). Üres DB → nincs adatmentés. **Fontos a bootstrap, különben a meglévő tesztek elhasalnak** (a séma ma kizárólag a `create_all`-ból jön):
- A `alembic upgrade head` fusson a szerver indulása **előtt** — a docker-compose backend entrypointjában **és** a pytest fixture-ökben (a tesztek élő szerver ellen futnak).
- A `server.py:56-59` ad-hoc `ALTER TABLE IF NOT EXISTS` sorok kivezetése — innentől a sémát az Alembic birtokolja.
- A `seed()` a migráció **után** fusson (és igazítsuk az új kötelező oszlopokhoz — ld. JV-15 az Ops-nál).

### 0.2 Activity irány-mező
- `models.py` — `Activity`: `direction = Column(String, nullable=True)` — `inbound`/`outbound`/`internal`/`NULL`.
- `schemas.py` — `ActivityBase`: `direction: Optional[Literal["inbound","outbound","internal"]] = None`.
- A `[Inbound]/[Outbound]` prefix-hack kikerül a kódból (nincs backfill, üres DB).
- `frontend`: irány-választó a Log email formon. Megjegyzés (audit A-6): a `DealDetail` ma **csak olvasható** — az iránnyal ellátott aktivitás-rögzítéshez ott egy net-új aktivitás-form kell, nem csak egy mező.

### 0.3 Generikus esemény-napló infrastruktúra
- `models.py` — új `EventLog` tábla:

  | Mező | Típus |
  |---|---|
  | id | String PK (`gen_id()`) |
  | entity_type | String, not null, indexelt — `deal` (később `project`, `milestone`, `contact`, …) |
  | entity_id | String, not null, indexelt (nincs DB-FK — több táblára mutathat; integritás kódban) |
  | event_type | String, not null — `created, claimed, stage_changed, status_changed, activity_logged, owner_changed, visibility_changed` |
  | from_value / to_value | String, nullable (pl. régi/új státusz — visszalépésnél is) |
  | actor_type | String — `user` vagy `service` (audit JV-8) |
  | actor_id | String, nullable (a user vagy service-account id-je; nincs DB-FK, mert principal-típus szerint más táblára mutat) |
  | activity_id | FK → `activities.id`, SET NULL, nullable |
  | note | String, nullable |
  | created_at | DateTime(tz), indexelt |

  Összetett index `(entity_type, entity_id, created_at)`.
- **`won`/`lost` nem külön event-típus** (audit JV-7): a megnyerés/elvesztés egy `stage_changed`, aminek a `to_value`-ja `won`/`lost` — így az analitika nem számol duplán. (Korábban külön `won`/`lost` típus is szerepelt; kivéve.)
- **Actor lehet ember VAGY service-account** (audit JV-8): ezért `actor_type`+`actor_id`, nem `users.id` FK — így a Fázis 6 MCP-ügynök műveletei is naplózhatók anélkül, hogy user-sornak kellene lennie.
- Közös helper `backend/utils.py`: `log_event(db, entity_type, entity_id, event_type, actor, from_value=None, to_value=None, ...)`. Minden write-pont ezen keresztül naplóz. **Append-only** — sosem íródik felül, így hiteles history, és a visszalépések is nyomon követhetők.
- **Írás vs. megjelenítés** (audit JV-17): az `EventLog` **írása minden `entity_type`-ra a 0.3-tól működik** (a generikus infra miatt — pl. a Fázis 1 `visibility_changed` projekten, a Fázis 4 `milestone` státuszok már ide írnak). A „bekapcsolás" (Nyitott döntés) csak arról szól, mely entitásokhoz készül **timeline-UI**.
- **Törlés-politika** (audit JV-14): mivel a törlés hard delete és nincs DB-FK, egy entitás törlésekor az `EventLog`-sorai megmaradnak (audit-cél). A `/timeline` végpont törölt entitásra 404 vagy „archivált" jelzést ad — ezt explicit kezeljük, nem hagyjuk lógó hibának.

**Miért 0. fázis:** a státuszváltás-naplózás (amit kértél a visszalépésekhez) minden későbbi fázist érint, ezért az infrastruktúra előre kell.

### 0.4 Séma-higiénia (MCP-enabler)
Olcsó, most elvégezhető javítások, amik később a generált MCP tool-sémákat pontossá teszik:
- `Literal` a hiányzó enum-mezőkre: `Project.priority` és `User.role` a `schemas.py`-ban (a report §2 és a „Nem egyértelmű pontok" #3 jelezte a hiányt).
- Minden végponthoz értelmes `summary` + `description` a FastAPI dekorátorban → ezekből lesznek az MCP tool-leírások.
- Egységes, strukturált hibaformátum (a meglévő `formatApiError` mellé konzisztens backend hibatörzs), hogy egy ügynök gépből is értse a hibát.
- **Meglévő tesztek frissítése** (audit JV-12): a `Literal` szigorítás viselkedést vált az API-határon — ma az érvénytelen enum alapértékre esik (AI-create), a `RegisterRequest.role` szabad string; `Literal` után 422 jön. A meglévő user-create/AI-create teszteket ehhez igazítani kell (a „minden teszt zöld" elv miatt a meglévők frissítése is a scope része, nem csak új teszt).

---

## Fázis 1 — Hozzáférés-kezelés

A négyrétegű modell megvalósítása (ld. fentebb). Azért ilyen korán, mert a láthatóság-szűrés és a pénz-maszkolás minden lista/detail végpontot érint — tisztább előbb lerakni, mint később minden endpointba visszavezetni.

- **Capability mátrix**: `AppSetting` `role_capabilities` JSON + kódbeli alapértékek; `require_capability()` dependency (`auth.py`); admin UI a Settings oldalon a mátrix szerkesztéséhez (`Settings.jsx`).
- **Objektum-láthatóság**: `visibility` mező a `Deal`/`Project`-en (`models.py`), alap a szervezeti beállításból; `set_visibility` képességhez kötve.
- **Membership**: `EntityMembership` tábla; owner auto-tag; meghívás UI a deal/projekt detailen (`invite_members` képességhez kötve); végpontok: `POST/DELETE /api/deals/{id}/members`, ugyanez projektre.
- **Láthatóság-szűrés (audit BL-2)** minden érintett olvasó úton — nem csak a fő listákon: `deals.py`, `projects.py` lista+detail, **`companies/{id}/detail`, `contacts/{id}/detail`** (kapcsolódó deal/projekt), `dashboard.py`, és a `data_io.py` CSV-export (ez utóbbira **capability/role-gate** is). Közös helper a `backend/utils.py`-ban.
- **Pénzügyi maszkolás (audit BL-3, „A" minta)**: pénz-mezők `Optional`-lá tétele a `*Out`-ban + közös serializer-dependency, ami null-oz `view_financials` híján; a `dashboard.py` KPI-k és a CSV-export külön kezelve (nem séma-alapúak).
- **Authz-precedencia (audit JV-13)**: a `require_capability` a fő döntő; a régi `require_role`/`require_write` (`auth.py:85-97`) vagy erre cserélődik, vagy egyértelműen alárendelt (a capability-réteg felülírja). Rögzítjük, hogy egy végponton melyik dönt, hogy ne legyen rés.
- **Ügynök-identitás (MCP-enabler)**: egy `ServiceAccount` / API-kulcs koncepció, ami principalként ugyanabba a capability-modellbe kötődik, mint a userek. Így egy majdani MCP szerver nem „userként lép be", hanem szűkített jogú, visszavonható identitással hív. Tárolás: kulcs-hash + hozzárendelt szerepkör/capability-k; auth a meglévő `auth.py` mellé egy `X-API-Key` (vagy bearer service-token) ág. A pénz-maszkolás és láthatóság-szűrés rá is érvényes.
- **Tesztek**: minden réteghez (mátrix-olvasás, private objektum rejtése nem-tagtól, pénz-maszkolás user/guest esetén, meghívás utáni hozzáférés, service-account szűkített jogai).

---

## Fázis 2 — Lead-tulajdon + labda-státusz + életút

### 2.1 Claim
- Lead létrehozásakor `owner_id` lehet `None` (közös inbox). `Deal`-hez `claimed_at`.
- **A create nem fogad `owner_id`-t kliens-inputként** (spoofing ellen, a jelenlegi minta szerint). Egy explicit `unassigned: bool` flag a create-payloadban dönt: `False` (alap) → az owner a létrehozó; `True` → közös inbox (`owner_id=None`). (audit JV-16)
- **`Deal.source` (D10)**: enum `inbound`/`outreach`/`referral`/`other`, a lead létrehozásakor megadva (a beajánló-követés `referred_by_contact_id` mellett — az utóbbi a `referral` forrás részletezője).
- `PATCH /api/deals/{id}/claim` → `owner_id=user.id`, `claimed_at=now`, `log_event(..., "claimed")`.
- **Owner-kötelezőség (audit BL-4)**: a `PATCH /stage` megtagadja a `qualified` fölé lépést, ha `owner_id IS NULL` (HTTP 400); a deal→projekt automatizmus (Fázis 4.3) szintén owner-t követel. A lead tehát maradhat gazdátlan az inboxban, de nem haladhat előre, amíg valaki el nem vállalja.
- Owner átállítás: `reassign_owner` képességhez kötve; `owner_changed` naplózás.
- **Gazdátlan-lead figyelmeztetés (audit JV-10)**: mivel a lusta minta `owner_id == user.id`-re szűr, egy gazdátlan lead senkihez sincs kötve — ezért a `auto_unclaimed_lead` a `view_all_reports` jogú userek (managerek) harangjában jelenik meg, nem senkiében. (Fázis 5-ben a napi job veszi át megbízhatóan.) Küszöb: **2 munkanap** (D7), globális, admin-állítható. Plusz egy közös „gazdátlan leadek" lista-nézet.

### 2.2 Labda-státusz
- `Deal`-hez: `last_contact_at`, `ball_in_court` (`us`/`them`/`none`). Iránnyal ellátott `Activity` create-kor frissül (`inbound`→`us`, `outbound`→`them`); kézi felülírás lehetséges.
- Lusta `auto_awaiting_response` notification (`ball_in_court='us'` és `last_contact_at` régebbi mint **5 munkanap** — D7).
- UI: labda-badge a listán és a kanban kártyákon; „Nálunk a labda" szűrő.

### 2.3 Életút-nézet + analitika (az EventLog-ra épül)
- `GET /api/deals/{id}/timeline` — `EventLog` (`entity_type='deal'`) + kapcsolt `Activity`-irány, időrendben. UI: „Életút" idővonal a `DealDetail.jsx`-en, összecsukható passz-sorozatokkal, fejlécben összesítők (átfutás, passz-szám, leghosszabb stádium).
- `GET /api/reports/deal-flow` (`view_all_reports` képességhez kötve) — átlagos passz-szám a megnyert dealekig, átlag idő stádiumonként, won/lost arány; `recharts`-tal megjelenítve.
- **Passz-definíció (audit JV-3)**: egy „passz" = a `ball_in_court` irányváltása (nálunk↔kliens). A „passz-szám" ezek darabszáma; az UI a hosszú passz-sorozatokat csukja össze. (A stádiumváltás és az aktivitás külön dimenzió, nem passz.)

---

## Fázis 3 — Lead-típus, szerződő fél, beajánló

- `Deal.lead_type`: `single`/`double` (`Literal`).
- Kétoldalúnál külön szerződő fél: `contract_company_id`, `contract_contact_id` (FK, SET NULL). A meglévő `company_id`/`contact_id` a napi kapcsolattartó (kétoldalúnál a közvetítő); egyoldalúnál a `contract_*` üres, és a `company_id`/`contact_id` a szerződő fél is.
- Beajánló: `Deal.referred_by_contact_id` (önhivatkozó FK a Contactra); „Rendszeres beajánló" a meglévő `Contact.tags` JSONB-ben; rollup a contact detailen (hány dealt hozott, ebből hány won) — kérés-időben számolt.
- UI: lead-típus választó + feltételes második blokk (`double`); „Beajánlotta" választó; beajánlások panel.
- **Stádium-guard: most nem** — a `contract_*` mezők léteznek, de a „won"-ba lépés nincs blokkolva. A guard helyét meghagyjuk (később egy `require`-szerű ellenőrzés a `PATCH /stage`-ben triviálisan bekapcsolható).

---

## Fázis 4 — Mérföldkövek, rugalmas számlázás, deal→projekt automatizmus

### 4.1 Milestone modell
- `models.py` — új `Milestone`: `project_id` (FK, CASCADE), `name`, `order_index`, `due_date`, `amount` (nullable), `percentage` (nullable), `work_status`, `payment_status`, `created_at`, `updated_at`.
- **Munka- és fizetési státusz külön** (kérésed szerint):
  - `work_status`: `in_progress → client_review → accepted` (a „client_review" fejezi ki a „teljesítettük, kliens elfogadására várunk" állapotot).
  - `payment_status`: `not_due → invoiceable → invoiced → paid` — teljesen független a munka-státusztól.
- **Visszaléptethető + naplózott**: mindkét státusz bármelyik irányba állítható; minden váltás `log_event(entity_type="milestone", ..., "status_changed", from_value, to_value)`.
- **`amount` VAGY `percentage`, nem mindkettő (audit JV-11)**: Pydantic-validátor (és lehetőség szerint DB check-constraint) kényszeríti, hogy pontosan az egyik legyen kitöltve. A százalékos mérföldkő összege futásidőben `percentage/100 * project.budget`.
- **Összeg vs. szerződéses érték (audit JV-2)**: fix-áras modellben a mérföldkövek összegének ki kell adnia a projekt `budget`-jét (= deal `value`). A rendszer nem tiltja az eltérést, de **figyelmeztet**, ha a mérföldkövek összege ≠ budget (elgépelés-védelem).
- Sablonok (konstans, a `STAGE_PROBABILITY` mintára): `single_final` (1 tétel 100%), `deposit_final` (előleg + zárás), `milestones` (szabad lista). Projekt-létrehozáskor előtölt, utána szerkeszthető.
- Router `backend/routers/milestones.py`: CRUD + `PATCH /milestones/{id}/status`.

### 4.2 Pénznem: HUF és EUR
- A `currency` mező már létezik dealenként/projektenként (alap EUR). Kiterjesztjük: a mérföldkő-`amount` a projekt pénznemét örökli; UI-n pénznem-választó (HUF/EUR) a deal/projekt formon.
- **Riportok**: pénznemenként külön összegzés (nem keverünk HUF-ot és EUR-t egy összegbe) — a `dashboard.py` és `reports.py` a pénz-aggregációt `currency` szerint bontsa.

### 4.3 Deal → Projekt automatizmus
- `Project.deal_id` (FK, SET NULL).
- `PATCH /deals/{id}/stage` → `won`: automatikus `Project` létrehozás (company/contact/contract_* átmásolva, `value→budget`, `currency` átvéve, owner + tagok átvéve, mérföldkövek a sablonból), `log_event(..., "stage_changed", to_value="won")`. Idempotens (ha már van projekt a dealhez, nem hoz létre másikat). **Owner kötelező** (audit BL-4): owner nélküli dealt nem lehet `won`-ra állítani (nincs kire örökíteni a projektet).

### 4.4 Cash-flow nézet
- Kérés-időben (nincs Invoice-tábla): `invoiced` de nem `paid` mérföldkövek összege **pénznemenként** (nincs HUF+EUR keverés); a százalékos mérföldkő összege `percentage/100 * project.budget`. Kártya a dashboardon (`view_financials` képességhez kötve). Mérföldkő-UI a `ProjectDetail.jsx`-en státusz-váltókkal.

> Teljes Invoice/Payment entitást (számlaszám, PDF, adó) szándékosan nem építünk — az igény a mérföldkő-szintű fizetési státusz követése, nem számlázó rendszer.

### 4.5 Időkövetés a fix-áras modellben (audit JV-1)
A megörökölt `hourly_rate`, `estimated_hours`, `TimeEntry.billable` és az utilization-riport **belső mérésre** marad: mennyi munka/óra ment a fix árba, mennyire kihasznált a csapat. A **kliens felé a mérföldkövek számláznak**, nem az óradíj. A `billable` flag innentől „belső költség-e vs. beszámítandó" jelölő, nem kliens-számlázási tétel. A UI-ban a projekt pénzügyi nézete a mérföldkő-alapú (cash-flow), az óradíjas kalkuláció csak a belső utilization-riportban jelenik meg — így nincs két, egymásnak ellentmondó pénzügyi nézet a kliensről.

---

## Fázis 5 — Ütemező + utókövetés + kihűlőben

### 5.1 Háttér-ütemező
- `APScheduler` (vagy `asyncio` háttértaszk a `startup` hookban, `server.py:139-141`). Egy napi „housekeeping" job, ami session-független.
- **Többinstance-korlát (audit JV-9)**: az in-process scheduler egyetlen backend-példány mellett tökéletes (ma ez a helyzet), de több példány esetén mindegyik lefuttatná a jobot → duplikáció. Rögzítjük a korlátot; ha valaha skálázni kell, egy leader-lock (pl. Postgres advisory lock) vagy dedikált scheduler-konténer a megoldás. Dev alatt a `--reload` is duplázhat — figyelni rá.

### 5.2 Utókövetés
- `Project`-hez: `closed_at`, `follow_up_days` (alap 60, projektenként állítható), `satisfaction_score` (nullable — audit JV-4). `status→completed`-kor `closed_at` beáll.
- A napi job: ahol `closed_at + follow_up_days <= now` és nincs még utókövetés-aktivitás → `Activity` (task) a projekt ownerének. Idempotens (dedup-jelzővel).
- Elégedettség + beajánló-hurok: a task lezárásakor rögzíthető az elégedettség (a `satisfaction_score`-ba, pl. 1–5 skála) és „ajánl-e valakit". Ha igen → **új Deal a közös inboxba** (`owner_id=None`, `unassigned=True`, `lead_type="single"` alapból), `referred_by_contact_id` = a kliens kontaktja, és a kontakt `referrer` taget kap (audit JV-5).

### 5.3 Kihűlőben + a lusta ellenőrzések megbízhatóvá tétele
- A napi job a `ball_in_court='us'` + **14 munkanapnál** (D7) régebben nem frissült dealeket egy tárolt `is_stale` jelzőre állítja (nem a `stage`-et írja át). A Fázis 2 lusta `auto_unclaimed_lead`/`auto_awaiting_response` ellenőrzései is átkerülhetnek/duplikálódhatnak a jobba, hogy ne függjenek attól, ki nyitja meg az appot.

---

## Fázis 6 — MCP szerver (AI-native hozzáférés)

Cél: egy MCP szerver a CRM fölé, amin keresztül egy AI-ügynök ugyanazokat a műveleteket biztonságosan eléri, mint egy ember. Az addigi fázisok már lerakták az enablereket (0.4 séma-higiénia, Fázis 1 service-account, `EventLog`), így ez a fázis magára a szerverre koncentrál.

### 6.1 Az MCP szerver felállítása
- Külön kis szolgáltatás (saját konténer a docker-compose-ban), ami a CRM REST API-jával beszél — nem a DB-vel közvetlenül, hogy minden üzleti szabály, capability-ellenőrzés és maszkolás egy helyen (a backendben) maradjon.
- Hitelesítés a Fázis 1 service-accounttal (`X-API-Key` / service-token). Az ügynök jogait az adminok a capability-mátrixban szabják, ugyanúgy, mint egy usernél.
- A tool-készlet generálható a FastAPI OpenAPI-sémából (a 0.4 után pontos), vagy kézzel egy szűk, jól leírt tool-halmaz — kezdetben a fontos műveletekre.

### 6.2 Első tool-készlet (javaslat)
- **Olvasó tool-ok**: leadek/dealek/projektek listázása és keresése szűrőkkel; egy entitás részletei; egy deal életútja (`/timeline`); pipeline-analitika (`/reports/deal-flow`).
- **Író tool-ok**: lead létrehozás, claim, stádium-váltás (naplózva), aktivitás rögzítése iránnyal (a labda-státusz frissül), mérföldkő-státusz állítása.
- Minden tool a service-account jogain belül fut; a pénzügyi mezők maszkolása és az objektum-láthatóság az ügynökre is érvényes.

### 6.3 Biztonság és korlátok
- Least-privilege alapon: az ügynök alap-jogköre szűk (pl. olvasás + aktivitás-rögzítés), a kockázatosabb írások (törlés, owner-átállítás, láthatóság-váltás) külön capability mögött.
- Minden ügynök-művelet ugyanúgy az `EventLog`-ba naplózódik, `actor` = a service-account — így visszakövethető, mit csinált az AI.
- Rate limit a meglévő `slowapi`-val az MCP-hívásokra is — **API-kulcs szerint kulcsolva** (audit A-7), nem IP szerint (a `slowapi` alapból `get_remote_address`-t használ, és az MCP-konténerből minden hívás egy IP-ről jönne → közös bucket).

> Megjegyzés: a meglévő in-app AI parancssor (`ai_service.py`) megmarad; az MCP szerver ettől független, kifelé nyitott réteg egy külső ügynöknek. A kettő ugyanazt a validációs elvet követi (szerver dönt, nem az LLM).

---

## Ops — backup

Mivel éles kliens-adat lesz benne, a Postgres alá kell egy mentési megoldás. Javasolt (növekvő komolyság szerint):

- **Minimum**: napi `pg_dump` egy külön kis konténerből vagy host-cronból (`docker exec <db> pg_dump ...`) egy mountolt kötetre, N napos retencióval. Egyszerű, a jelenlegi docker-compose mellé illeszthető.
- **Jobb**: a dump feltöltése egy off-site tárolóba (pl. objektumtár / másik gép), hogy egy diszk-hiba ne vigye el a mentést is.
- **Vissza-állítás próba**: érdemes néha ténylegesen visszatölteni egy dumpot egy külön adatbázisba — a nem tesztelt backup nem backup.
- A seed/demo adatokat (`server.py:53-136`) éles indulás előtt ki kell venni vagy egy flag mögé tenni, hogy ne kerüljön demo-adat az éles bázisba.
- **Seed-karbantartás fázisközben (audit JV-15)**: minden fázis, ami új kötelező oszlopot vagy kapcsolatot ad (pl. `visibility`, membership-sorok, `direction`), frissítse a `seed()`-et is — különben az induló bootstrap és a seedre támaszkodó tesztek elhasalnak. Ez nem csak éles-indulási teendő.

---

## Összegző implementációs sorrend

1. **Fázis 0**: Alembic baseline · `Activity.direction` · `EventLog` + `log_event` helper · séma-higiénia (`Literal`-ok, OpenAPI leírások, strukturált hibák).
2. **Fázis 1**: capability mátrix (`AppSetting` + `require_capability` + admin UI) · objektum-láthatóság (`visibility`) · `EntityMembership` + meghívás · láthatóság-szűrés · pénzügyi maszkolás · service-account/API-kulcs (MCP-enabler).
3. **Fázis 2**: claim + gazdátlan-nézet · labda-státusz + badge + emlékeztetők · életút-timeline + deal-flow analitika.
4. **Fázis 3**: `lead_type` + `contract_*` · beajánló (`referred_by_contact_id` + tag + rollup). Guard még nem.
5. **Fázis 4**: `Milestone` + sablonok + külön/visszafordítható/naplózott státuszok · HUF/EUR · deal→projekt automatizmus · cash-flow.
6. **Fázis 5**: APScheduler · utókövetés + elégedettség/beajánló-hurok · kihűlőben.
7. **Fázis 6**: MCP szerver a CRM fölé · service-account auth · olvasó/író tool-készlet · least-privilege + naplózás.
8. **Ops**: backup + demo-adat kivétele éles indulás előtt.

Minden fázis akkor kész, ha a tesztjei zölden futnak; a commitok fázison belül funkciónként külön.

---

## Rögzített döntések (mind jóváhagyva — ezek a kötelező alapértékek)

Ezek NEM nyitott kérdések többé — az implementáció ezekkel az értékekkel készül. Ahol „admin által állítható" szerepel, ott ez a **default**, amit az admin később módosíthat.

| # | Döntés | Rögzített érték |
|---|---|---|
| D1 | Owner-kötelezőség (BL-4) | Gazdátlan maradhat az inboxban, de **nem léphet `qualified` fölé**, és projekthez owner kell. |
| D2 | Pénzügyi maszkolás módja (BL-3) | „A" minta — `Optional` mezők + közös nullázó serializer-dependency. |
| D3 | Időkövetés szerepe (JV-1) | Belső költség/kihasználtság; a kliens felé a mérföldkövek számláznak. |
| D4 | Passz-metrika (JV-3) | A `ball_in_court` irányváltásainak száma. |
| D5 | Láthatóság-alapértelmezés | Új deal/projekt alapból **`public`**. |
| D6 | `view_financials` default | `admin` ✅, `manager` ✅, `user` ✅ (be), `guest` ❌ (ki). |
| D7 | Küszöbök (munkanapban, globális, admin-állítható) | Gazdátlan: **2** · `awaiting` (ránk vár): **5** · `stale` (kihűlőben): **14**. |
| D8 | Kétoldalú labda-szál | Egyelőre **egy szál** dealenként. |
| D9 | EventLog timeline-UI sorrend | Deal először, utána **projekt** (a naplózás minden típusra megy a 0.3-tól). |
| D10 | `Deal.source` mező (A-1) | **Igen** — egyszerű enum: `inbound`, `outreach`, `referral`, `other`. |
| D11 | Mérföldkő összeg (JV-11) | `amount` VAGY `percentage`, pontosan az egyik. |

> **Elfogadott kockázat (audit A-3)**: a `visibility`/tagság csak dealen és projekten van; a **kontaktok és cégek minden bejelentkezettnek láthatók** (kliens-PII, beajánló-háló is). Tudatos egyszerűsítés 6 fős csapatnál — később a membership-minta rájuk is kiterjeszthető.

> A Google Workspace integráció (SSO, Gmail/Calendar auto-napló) — külön kérésre — **kimarad**. A `google_*` mezők holt mezők maradnak; ha később kell, önálló projekt.