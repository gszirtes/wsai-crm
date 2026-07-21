Egy meglévő CRM-et bővítesz (FastAPI + SQLAlchemy 2.0 + Pydantic v2 + PostgreSQL backend, React 18 frontend, Docker Compose). A teljes terv az `INTEGRATION_PLAN.md`-ben van a repó gyökerében — **ez a source of truth**, minden mező, végpont és fázis részlete ott van. A te dolgod a tervet **fázisonként, lépésről lépésre** megvalósítani.

## Alapszabályok (mindvégig tartsd be)

1. **Olvasd el először a teljes `INTEGRATION_PLAN.md`-t**, és minden lépésnél a hozzá tartozó szakaszt. Ne térj el a tervtől; ha ellentmondást vagy hiányt találsz, **állj meg és kérdezz**, ne találgass.
2. **Külön feature-branch** minden fázishoz (pl. `feat/phase-0-foundations`). Ne dolgozz a fő ágon.
3. **Definition of done = minden teszt zöld.** Egy lépés csak akkor kész, ha a hozzá írt/frissített pytest integrációs tesztek (a meglévő `backend/tests/` minta szerint, élő szerver ellen) zölden futnak. Új funkció = új teszt; ha egy meglévő teszt viselkedése jogosan változik, frissítsd.
4. **Funkciónkénti commit.** Egy fázison belül minden logikai egység külön commit, beszédes üzenettel (pl. `feat(phase1): capability matrix + require_capability dependency`).
5. **STOP minden fázis (és a Step 0) végén.** Írd ki röviden, mit csináltál, milyen teszteket futtattál és azok eredményét, majd **várd meg a jóváhagyást**, mielőtt a következő fázisba kezdesz. Ne ugorj előre.
6. **Ne rontsd el a meglévő működést.** A refaktorok (pl. `create_all` → Alembic, enum `Literal`-ok) érinthetnek meglévő teszteket — ezeket tudatosan, a tervben leírtak szerint kezeld.
7. **Ne implementálj olyat, ami a tervben nincs** (pl. Google Workspace integráció kifejezetten kimarad; teljes Invoice/Payment modell nem épül).

## Rögzített döntések (ezekkel az értékekkel dolgozz — nem nyitottak)

- **D1** Owner-kötelezőség: gazdátlan lead maradhat az inboxban, de nem léphet `qualified` fölé, és projekt-létrehozáshoz owner kell.
- **D2** Pénzügyi maszkolás: „A" minta — a pénz-mezők `Optional`-ek a `*Out` sémákban, egy közös serializer-dependency null-ozza őket `view_financials` híján.
- **D3** Időkövetés: belső költség/kihasználtság-mérés; a kliens felé a mérföldkövek számláznak (nem az óradíj).
- **D4** „Passz" = a `ball_in_court` irányváltásainak száma.
- **D5** Új deal/projekt láthatóság alapból `public` (admin módosíthatja a globális defaultot).
- **D6** `view_financials` default: admin ✅, manager ✅, user ✅, guest ❌.
- **D7** Küszöbök (munkanap, globális, admin-állítható): gazdátlan **2**, `awaiting` **5**, `stale` **14**.
- **D8** Kétoldalú labda: egyelőre egy szál dealenként.
- **D9** EventLog timeline-UI: deal először, utána projekt (a naplózás minden `entity_type`-ra megy a Fázis 0-tól).
- **D10** `Deal.source` enum: `inbound`/`outreach`/`referral`/`other`.
- **D11** Mérföldkő: `amount` VAGY `percentage`, pontosan az egyik.

---

## STEP 0 — Előkészítés és dokumentáció (ezzel kezdd)

**Cél:** tiszta kiindulás + a projekt „memóriájának" (CLAUDE.md / agent-doksi) frissítése, hogy minden későbbi session ismerje az új architektúrát.

**Teendők:**
1. Olvasd el a teljes `INTEGRATION_PLAN.md`-t.
2. Hozz létre egy branch-et: `feat/crm-v2-setup`.
3. **Futtasd le a meglévő teszteket a jelenlegi kódon** (`backend/tests/`). Ha nem zöld a kiindulás, állj meg és jelentsd — ne kezdj fejlesztésbe piros baseline-ról.
4. **Frissítsd a `CLAUDE.md`-t** a repó gyökerében az új architektúrával és konvenciókkal, hogy a jövőbeli munkамenetek is ismerjék:
   - Az új adatmodell-elemek: `EventLog` (generikus, `entity_type`+`entity_id`, append-only), `EntityMembership`, `Milestone`, `ServiceAccount`, valamint az új mezők (`Deal.visibility/lead_type/contract_*/referred_by_contact_id/source/ball_in_court/last_contact_at/claimed_at/is_stale`, `Activity.direction`, `Project.deal_id/closed_at/follow_up_days/satisfaction_score`).
   - A jogosultsági modell: 4 réteg (szerepkör → objektum-láthatóság → membership → capability-mátrix az `AppSetting`-ben), és a `require_capability()` használata.
   - Konvenciók: minden státusz/enum mezőn Pydantic `Literal`; minden write-pont `log_event()`-en át naplóz; pénzügyi maszkolás a közös serializer-dependency-vel; migráció **Alembic**-kel (nincs több `create_all` / ad-hoc `ALTER TABLE`).
   - Munkamódszer: tesztelés mint DoD, funkciónkénti commit, fázisonkénti szállítás.
   - A rögzített döntések (D1–D11).
5. Ha a projekt használ **`AGENTS.md`**-t (vagy hasonló agent-konfigot), hozd létre/frissítsd ugyanezekkel a konvenciókkal, tömören.
6. Commit: `docs: CLAUDE.md + AGENTS.md frissítés a CRM v2 architektúrával és konvenciókkal`.

**Elfogadási kritérium:** a baseline tesztek zöldek; a CLAUDE.md tükrözi az új architektúrát és a D1–D11-et.

**STOP** — jelentsd az eredményt, várj jóváhagyásra.

---

## STEP 1 — Fázis 0: Alapok (enablerek)

Terv: `INTEGRATION_PLAN.md` → „Fázis 0". Branch: `feat/phase-0-foundations`.

**Al-lépések (mind külön commit):**
1. **0.1 Alembic bevezetése** — `alembic init`, egyetlen baseline a jelenlegi sémáról; a `create_all` (`server.py:54`) kiváltása; `alembic upgrade head` a docker-compose backend entrypointban **és** a pytest fixture-ökben; a `server.py:56-59` ad-hoc `ALTER TABLE` kivezetése; a `seed()` a migráció után fut. **A meglévő teszteknek ezek után is zöldnek kell lenniük.**
2. **0.2 `Activity.direction`** mező (`inbound`/`outbound`/`internal`/NULL) + Pydantic `Literal`; a `[Inbound]/[Outbound]` prefix-hack eltávolítása; frontend irány-választó (a DealDetailen ez net-új aktivitás-form — ld. terv).
3. **0.3 `EventLog` tábla** a terv szerinti mezőkkel (`entity_type`, `entity_id`, `event_type`, `from_value`/`to_value`, `actor_type`+`actor_id`, `activity_id`, `note`, `created_at`; összetett index). Közös `log_event()` helper a `backend/utils.py`-ba. `won`/`lost` NEM külön event (az egy `stage_changed`, `to_value=won/lost`). Törlés-politika: az `EventLog`-sorok megmaradnak, a `/timeline` törölt entitásra „archivált"/404-et ad.
4. **0.4 Séma-higiénia** — `Literal` a `Project.priority` és `User.role` mezőkre; `summary`+`description` minden végponton; egységes strukturált hibaformátum. **A meglévő user-create/AI-create teszteket frissítsd** (az érvénytelen enum mostantól 422, nem fallback).

**Elfogadási kritérium:** friss adatbázis Alembickel felépül; minden meglévő és új teszt zöld; a `log_event()` működik és egy stádiumváltás megjelenik az `EventLog`-ban.

**STOP** — jelentés + jóváhagyás.

---

## STEP 2 — Fázis 1: Hozzáférés-kezelés

Terv: „Fázis 1" + „Hozzáférés-kezelési modell". Branch: `feat/phase-1-access-control`.

**Al-lépések (külön commitok):**
1. **Capability-mátrix**: `role_capabilities` JSON az `AppSetting`-ben + kódbeli default (D6 értékekkel); `require_capability()` dependency; admin UI a Settings oldalon.
2. **Objektum-láthatóság**: `visibility` mező `Deal`/`Project`-en, globális default `public` (D5), `set_visibility` capability-hez kötve.
3. **`EntityMembership`** tábla + owner auto-tag + meghívás UI és végpontok (`invite_members`-hez kötve).
4. **Láthatóság-szűrés (BL-2)**: közös helper, és rátéve MINDEN érintett olvasó útra — `deals.py`, `projects.py`, `companies/{id}/detail`, `contacts/{id}/detail`, `dashboard.py`, valamint a `data_io.py` CSV-export (utóbbira capability/role-gate is).
5. **Pénzügyi maszkolás (D2)**: pénz-mezők `Optional` a `*Out`-ban + közös nullázó serializer-dependency; a `dashboard.py` és a CSV-export külön kezelve.
6. **Authz-precedencia (JV-13)**: rögzítsd, hogy a `require_capability` a fő döntő; a régi `require_role`/`require_write` erre cserélődik vagy egyértelműen alárendelt.
7. **`ServiceAccount` / API-kulcs** (MCP-enabler): principal a capability-modellben, `X-API-Key` auth-ág a meglévő `auth.py` mellett.

**Elfogadási kritérium (tesztek):** private objektum rejtve nem-tagtól minden úton (a companies/contacts detailen és CSV-n is); pénz-mezők maszkolva `user`/`guest` esetén; meghívás után hozzáférés; service-account szűkített jogai. Mind zöld.

**STOP** — jelentés + jóváhagyás.

---

## STEP 3 — Fázis 2: Lead-tulajdon + labda-státusz + életút

Terv: „Fázis 2". Branch: `feat/phase-2-ownership-ball`.

**Al-lépések:**
1. **Claim**: `owner_id` nullable + `claimed_at`; `unassigned` flag a create-ben (owner_id sosem kliens-input); `PATCH /deals/{id}/claim`; owner-átállítás `reassign_owner`-hez kötve; `Deal.source` (D10) a create-ben.
2. **Owner-kötelezőség (D1)**: `PATCH /stage` megtagadja a `qualified` fölé lépést `owner_id IS NULL` esetén.
3. **Labda-státusz**: `last_contact_at` + `ball_in_court`; iránnyal ellátott `Activity` create-kor frissül; kézi felülírás; badge + „Nálunk a labda" szűrő a UI-n.
4. **Emlékeztetők (lusta)**: `auto_unclaimed_lead` (2 munkanap, managerek harangjában — D7/JV-10) + `auto_awaiting_response` (5 munkanap — D7).
5. **Életút + analitika**: `GET /deals/{id}/timeline` + „Életút" idővonal a DealDetailen; `GET /reports/deal-flow` (`view_all_reports`-hoz kötve). Passz = `ball_in_court` váltás (D4).

**Elfogadási kritérium:** claim és owner-guard működik; a labda-státusz helyesen frissül iránytól; az emlékeztetők a megfelelő címzettnek jelennek meg; a timeline időrendben adja az eseményeket. Tesztek zöldek.

**STOP** — jelentés + jóváhagyás.

---

## STEP 4 — Fázis 3: Lead-típus, szerződő fél, beajánló

Terv: „Fázis 3". Branch: `feat/phase-3-lead-type-referral`.

**Al-lépések:** `Deal.lead_type` (`single`/`double`); `contract_company_id`/`contract_contact_id`; feltételes második UI-blokk `double`-nél; `referred_by_contact_id` (önhivatkozó FK) + „Rendszeres beajánló" tag + rollup a contact detailen. **Stádium-guard MOST nem** — csak a mezők, a blokkolás nem.

**Elfogadási kritérium:** egy- és kétoldalú lead helyesen kezelt; a beajánló-rollup helyes számot ad. Tesztek zöldek.

**STOP** — jelentés + jóváhagyás.

---

## STEP 5 — Fázis 4: Mérföldkövek, számlázás, deal→projekt

Terv: „Fázis 4". Branch: `feat/phase-4-milestones-billing`.

**Al-lépések:**
1. **`Milestone` modell** + `milestones.py` router (CRUD + `PATCH /status`); külön `work_status` és `payment_status`; visszaléptethető + `log_event`-tel naplózott; `amount` VAGY `percentage` validáció (D11).
2. **Sablonok**: `single_final` / `deposit_final` / `milestones`; projekt-létrehozáskor előtölt.
3. **Összeg vs. budget figyelmeztetés** (JV-2); százalék→pénz: `percentage/100 * budget`.
4. **HUF/EUR**: pénznem-választó; riportok pénznemenként bontva (nincs keverés).
5. **Deal→Projekt (D1/BL-4)**: `Project.deal_id`; `won`-ra automatikus projekt (owner kötelező); idempotens.
6. **Cash-flow** nézet (invoiced-nem-paid, pénznemenként); mérföldkő-UI a ProjectDetailen.
7. **Időkövetés (D3)**: az óradíjas rész belső utilizationra marad, kliens felé a mérföldkövek.

**Elfogadási kritérium:** a három sablon helyesen tölt; státusz-visszalépés naplózódik; a won→projekt egyszer fut le; a cash-flow pénznemenként helyes. Tesztek zöldek.

**STOP** — jelentés + jóváhagyás.

---

## STEP 6 — Fázis 5: Ütemező + utókövetés + kihűlőben

Terv: „Fázis 5". Branch: `feat/phase-5-scheduler-followup`.

**Al-lépések:** APScheduler napi „housekeeping" job (dokumentáld a többinstance-korlátot — D/JV-9); `Project.closed_at`/`follow_up_days` (alap 60)/`satisfaction_score`; utókövetés-task generálás (idempotens); elégedettség + beajánló-hurok (új deal a közös inboxba, `referrer` tag — JV-5); `is_stale` jelző 14 munkanapnál (D7); a lusta ellenőrzések átemelése a jobba (ne duplikáljon).

**Elfogadási kritérium:** a napi job lefut és létrehozza az esedékes utókövetés-taskot; nincs dupla értesítés; az `is_stale` helyesen áll be. Tesztek zöldek.

**STOP** — jelentés + jóváhagyás.

---

## STEP 7 — Fázis 6: MCP szerver

Terv: „Fázis 6". Branch: `feat/phase-6-mcp-server`.

**Al-lépések:** külön MCP-szolgáltatás (saját konténer), ami a CRM **REST API-t** hívja (nem a DB-t); auth a Fázis 1 service-accounttal; olvasó + író tool-készlet (ld. terv 6.2); least-privilege (kockázatos írások külön capability mögött); minden ügynök-művelet `log_event`-tel (`actor_type=service`); rate limit API-kulcs szerint kulcsolva (A-7).

**Elfogadási kritérium:** egy AI-ügynök a service-accounttal listázni és aktivitást rögzíteni tud; a pénz-maszkolás és láthatóság rá is érvényes; minden művelet megjelenik az `EventLog`-ban. Tesztek zöldek.

**STOP** — jelentés + jóváhagyás.

---

## STEP 8 — Ops: backup + éles előkészítés

Terv: „Ops — backup". Branch: `chore/ops-backup`.

**Al-lépések:** napi `pg_dump` (külön konténer/host-cron) mountolt kötetre, retencióval; off-site másolat; visszaállítás-próba dokumentálva; a `seed()`/demo-adat flag mögé vagy kivéve éles indulás előtt.

**Elfogadási kritérium:** a backup lefut és egy dump visszatölthető egy külön adatbázisba. 

**STOP** — végső jelentés.

---

## Ha elakadsz vagy ellentmondást találsz

Ne találgass és ne térj el a tervtől. Állj meg, írd le pontosan, mi a kérdés/ellentmondás (a terv melyik szakaszához képest), és kérj döntést, mielőtt folytatod.