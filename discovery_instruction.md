Végezz egy teljes körű, csak-olvasás jellegű állapotfelmérést ennek a repónak a CRM implementációjáról. A cél: pontos, kódból visszakövethető leltár arról, mi van *jelenleg* megvalósítva — funkciók és adatmodell egyaránt —, hogy ezt később egy célállapot-tervhez tudjuk hasonlítani. Ne javasolj még módosítást, ne értékelj, ne kritizálj — csak térképezd fel és dokumentáld, ami ténylegesen a kódban van.

Ha valami nem egyértelmű a kódból (pl. egy mező célja, egy állapotgép átmenete, vagy egy funkció be van-e kötve a UI-ba), ezt írd ki explicit módon "nem egyértelmű a kódból" jelöléssel — ne találgass, és ne egészítsd ki feltételezésekkel.

Minden megállapításhoz add meg a forrás fájl elérési útját (és ha releváns, sor- vagy szekció-hivatkozást), hogy vissza lehessen keresni.

## 1. Áttekintés

- Tech stack (backend, frontend, adatbázis, főbb library-k).
- Repó/mappa struktúra rövid összefoglalása (hol vannak a modellek, route-ok, UI komponensek).
- Hogyan fut/indul a projekt (ha kiderül configból vagy README-ből).

## 2. Adatmodell

Listázz **minden** entitást/táblát/modellt/collection-t, amit találsz (adatbázis séma, migrációk, ORM modellek, típusdefiníciók). Minden entitáshoz:

- Mezők listája típussal (pl. string, enum, dátum, kapcsolat más entitáshoz).
- Kapcsolatok más entitásokhoz (1:1, 1:N, N:M), és hogy ez hol van definiálva (foreign key, join tábla, embedded dokumentum stb.).
- Enum / választható érték listák (pl. stádium-értékek, típus-mezők) — a pontos lehetséges értékekkel, ahogy a kódban szerepelnek.
- Van-e soft delete, audit log, verziózás bármelyik entitáson.

## 3. Üzleti logika / állapotgépek

- Milyen "stádium" vagy "státusz" mezők vannak (pl. lead/deal stádium, projekt fázis, mérföldkő/fizetés státusz), és milyen konkrét értékeket vehetnek fel.
- Vannak-e kódban rögzített átmeneti szabályok (pl. "X státuszból csak Y-ba lehet lépni", validáció, guard-ek), vagy a státusz szabadon írható?
- Van-e valamilyen "ki a felelős / owner" mező bármelyik entitáson, és hogyan/mikor kerül kitöltésre (kézi vagy automatikus).

## 4. Automatizmusok, ütemezett feladatok, értesítések

- Vannak-e cron job-ok, scheduled task-ok, worker-ek, queue-consumer-ek.
- Vannak-e automatikus emlékeztetők, follow-up task-generálás, "X nap után történjen valami" jellegű logika.
- Vannak-e trigger-ek, amik egy entitás állapotváltozásakor más entitást hoznak létre vagy módosítanak (pl. "deal → won" hatására létrejön-e projekt rekord).
- Email/Slack/egyéb kimenő értesítések: mi váltja ki őket, milyen csatornán mennek.

## 5. Kommunikáció / kapcsolattartás nyomon követése

- Van-e bármilyen "interakció napló", "aktivitás log", "note", "timeline" jellegű funkció egy kliens/lead/projekt alatt.
- Van-e bármi, ami azt jelzi, ki felé "áll a labda" (pl. utolsó kontakt iránya, utolsó aktivitás dátuma, "várakozás" jelző).

## 6. Mérföldkövek és számlázás

- Van-e mérföldkő / fázis / szakasz modell projekteken, és mennyire rugalmas (fix sablon vs. szabadon szerkeszthető lista).
- Van-e fizetés / számla / invoice modell, és hogyan kapcsolódik a projekthez vagy mérföldkövekhez.
- Van-e fizetési státusz mező, és milyen értékeket vehet fel.

## 7. Beajánlás / kapcsolati háló

- Van-e "referrer", "beajánló", "forrás" mező bármelyik entitáson.
- Van-e olyan funkció, ami összeköt egy kontaktot több lead-del/dellel (pl. "hány leadet hozott ez a kontakt").
- Van-e külön kezelve az az eset, amikor a kapcsolattartó és a szerződő/fizető fél különböző személy/cég.

## 8. Jogosultságok / szerepkörök

- Van-e user/role modell, milyen jogosultsági szintek vannak.
- Ki láthat mit (pl. árak, fizetési adatok elérhetők-e mindenki számára).

## 9. API felület

- Listázd az összes elérhető API végpontot (route, HTTP metódus, rövid cél), csoportosítva entitásonként.

## 10. UI / felhasználói folyamatok

- Milyen fő képernyők/nézetek vannak (pl. lead lista, kanban board, projekt részletek).
- Melyik funkciók vannak ténylegesen bekötve a UI-ba, és melyik van csak a backend/adatmodellben, de UI-ból nem elérhető (ez fontos különbség).

## 11. Ismert hiányosságok, TODO-k, dead code

- Grep-eld át TODO / FIXME / HACK kommenteket, és listázd relevanciával.
- Jelezz minden olyan modellt/mezőt/funkciót, ami definiálva van, de sehol nem használt (halott kód gyanú).

## Kimeneti formátum

Strukturált Markdown riport, pontosan a fenti 11 szekcióval ebben a sorrendben. Táblázatokat használj az entitás-mezők és az API-végpontok listázásához. A riport végén egy rövid, külön szakaszban (**"Nem egyértelmű pontok"**) gyűjtsd össze mindazt, amit nem tudtál egyértelműen megállapítani a kódból, és minek járnátok utána emberi visszaigazolással.