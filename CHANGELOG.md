# Changelog

Formát vychází z [Keep a Changelog](https://keepachangelog.com/cs/1.1.0/).

---

## [2.8] — 2026-07-20

### Přidáno
- `PRIRUCKA_UZIVATELE.md` — uživatelská příručka rozdělená podle rolí (Uživatel / Administrátor), se screenshoty klíčových obrazovek v `docs/screenshots/`
- Interaktivní webová verze příručky (přepínač role, permission matrix, náhledy obrazovek)

---

## [2.7] — 2026-07-17

### Opraveno
- `dej_zarizeni(id)` v `data_funkce.py` — SQL parametr `(id)` (jednoprvková závorka bez čárky, ne tuple) sjednocen na `(int(id),)`; doplněn chybějící `finally: conn.close()` (dřív se spojení při úspěchu nezavíralo)

### Odstraněno (úklid technického dluhu)
- `mqtt/routes.py` — nepoužívaný pozůstatek z dřívější Flask implementace (Flask ani není v `requirements.txt`)
- `ensure_device_access_table()`, `ensure_train_types_table()`, `ensure_conditions_table()` v `data_funkce.py` — duplicitní vůči `init_db()`, nikde volané
- `save_packet_to_db()` v `data_funkce.py` — nikdy volaná (zapisovala do fakticky nevyužívané tabulky `mqtt_packets`)
- `_require_admin()` v `auth/devices.py` — definovaná, ale nikde použitá

### Změněno
- Databáze typů vlaků pro klasifikaci (15 lokomotiv) sjednocena do jediného zdroje pravdy — `nastaveni.TRAIN_TYPES_SEED`. Dřív existovala duplicitně jako `_TRAIN_DB_SEED` v `data_funkce.py` (skutečně používaný seed) a `_TRAIN_DB_FALLBACK` v `classifier.py` (záložní data pro degradovaný provoz) — riziko rozjetí při budoucí úpravě jednoho bez druhého
- Sjednoceno vynucování administrátorské role: `/auth/train-types*` (5 endpointů) a `/auth/admin/*` (4 endpointy) nyní používají `Depends(ma_roli("admin"))` místo ručního `if not current_user.admin` v těle funkce
- `ma_roli()` dependency (`decorators.py`) nyní při chybějící roli nastaví flash zprávu s vysvětlením, než vyhodí `NotAuthorizedException` — dřív u většiny takto chráněných endpointů uživatel jen tiše skončil jinde bez vysvětlení
- Globální handler `NotAuthorizedException` (`app.py`) přesměrovává na `/auth/dashboard` místo `/auth/login` — přihlášený uživatel bez potřebné role tak není zmatený neočekávaným „odhlášením“

Ověřeno automatizovaným smoke testem (`TestClient`): admin i běžný uživatel, přístup/zamítnutí na všech nově sjednocených endpointech, přítomnost flash zprávy, konzistence seedu databáze typů vlaků a shoda `classifier.py` fallbacku s `nastaveni.TRAIN_TYPES_SEED`.

---

## [2.6] — 2026-07-17

### Zabezpečeno
- `GET /add-user` se natrvalo uzamkne, jakmile v databázi existuje alespoň jeden uživatel (dřív bylo trvale a bez autentizace dostupné komukoli)
- `GET/POST /auth/user/{id}` nyní vyžaduje roli `admin` (dřív stačilo pouhé přihlášení — libovolný uživatel mohl měnit jméno, heslo i role kohokoli jiného, včetně přiřazení role admin sám sobě)
- `GET /auth/stats` nyní vyžaduje přihlášení (dřív veřejně dostupné bez autentizace)
- MQTT přihlašovací údaje (`MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`) přesunuty z natvrdo zapsaných hodnot v `mqtt_receiver.py` do konfigurace přes proměnné prostředí (`nastaveni.py`), s fallbackem na původní hodnoty sdíleného kurzovního brokeru
- Rate-limiting přihlášení: po 5 neúspěšných pokusech na stejné přihlašovací jméno se `POST /auth/login` na 60 s zamkne (in-memory, per proces)

Ověřeno automatizovaným smoke testem (`fastapi.testclient.TestClient`) proti reálně nastartované aplikaci.

---

## [2.5] — 2026-07-17

### Opraveno
- `dej_zarizeni()` v `data_funkce.py`: chybný SQL parametr `(id)` (string místo tuple) způsoboval u dvouciferných a delších `device_id` pád na „Incorrect number of bindings supplied“, tichým odchycením výjimky vedl k prázdnému zobrazení stránek „Správa zařízení“ a „Data zařízení“ — opraveno na `(int(id),)`
- `dej_zarizeni()`: chybějící `()` u `conn.close` (byl jen odkaz na metodu, spojení se nikdy nezavřelo) — přesunuto do `finally: conn.close()`

---

## [2.4] — 2026-06-25

### Opraveno
- Timeout packet bufferu měří nyní rozestup mezi pakety (ne celkový čas přenosu) — `buffer_timestamps` se aktualizuje při každém přijatém paketu, takže pomalý ale kontinuální přenos nevyprší předčasně

### Změněno
- `BUFFER_TIMEOUT_SECONDS` přesunuto z `mqtt_receiver.py` do `nastaveni.py` pro snazší konfiguraci

---

## [2.3] — 2026-06-24

### Přidáno
- Zelený indikátor „UNIT ALIVE" v hlavičce karty zařízení na dashboardu — zobrazuje čas posledního heartbeatu; tečka je zelená (< 10 min) nebo šedá (starší); aktualizuje se automaticky každých 15 s

---

## [2.2] — 2026-06-24

### Opraveno
- Tlačítko „← Zpět na seznam" v detailu MQTT logu nyní používá styl `btn btn-sm btn-secondary` shodně s ostatními tlačítky v aplikaci

---

## [2.1] — 2026-06-24

### Přidáno
- Denní MQTT log: každý den vznikne soubor `db/mqtt_logs/YYYY-MM-DD.log` se záznamy všech příchozích zpráv
- Logované události: `COMPLETE` (zpráva sestavena), `INCOMPLETE` (timeout), `REJECTED` (neregistrované zařízení), `PARSE_ERR` (chyba rozbalení paketu), `CLASSIFY_ERR` (chyba klasifikace)
- Admin stránka `/auth/admin/mqtt-log` — seznam denních souborů s možností rozkliknutí
- Detail logu `/auth/admin/mqtt-log/YYYY-MM-DD.log` — tabulka událostí s barevným odlišením typů (read-only, bez mazání)
- Položka „MQTT log" v administrátorském menu

---

## [2.0] — 2026-06-24

### Opraveno
- Klíč packet bufferu přepracován: místo času příchodu na server se jako klíč session používá `packet.timestamp` ze zařízení — opravuje bug, kdy přijde paket #1 pozdě (retransmise) a resetuje session, což osiřelé pakety 2–N posílá do timeoutu jako `_incomplete`
- `_device_session` nově klíčován dvojicí `(device_id, device_ts)` místo pouhého `device_id` — umožňuje korektní zpracování více transmisí z jednoho zařízení zároveň
- Název `.bin` souboru nyní odráží čas měření ze zařízení, ne čas příchodu na server

---

## [1.9] — 2026-06-19

### Přidáno
- Ukládání nekompletních zpráv po vypršení assembler timeoutu — místo zahazení se dostupné pakety spojí, uloží do `.bin` souboru s příponou `_incomplete` a zapíší do DB s příznakem `is_complete = 0`
- Sloupec `is_complete` v tabulce `messages` (migrace přes `ALTER TABLE` při startu)
- Badge „nekompletní" v seznamu průjezdů (žlutý, s tooltipem) pro záznamy s `is_complete = 0`
- CSS třída `.badge-incomplete`

---

## [1.8] — 2026-06-17

### Opraveno
- Čas posledního průjezdu vlaku zobrazován v českém čase místo UTC; `CURRENT_TIMESTAMP` (vždy UTC) nahrazen `COALESCE(measured_at, datetime(assigned, 'localtime'))` ve dvou SQL dotazech v `data_funkce.py`

---

## [1.7] — 2026-06-17

### Přidáno
- Chybový log aplikace: chyby se zapisují do souboru `db/app_error.log` (rotující, max 2 MB × 3 zálohy)
- Middleware `_ErrorLoggingMiddleware` zachycuje všechny neošetřené HTTP výjimky a loguje je s traceback
- Logování MQTT chyb: selhání rozbalení paketu, chyby klasifikace
- Admin stránka `/auth/admin/error-log` — zobrazí posledních 150 záznamů v tabulce, barevně odlišuje ERROR / WARNING, možnost vymazání logu
- Položka „Chybový log" v administrátorském menu
- Podpora obou formátů SYS telemetrie: **V1** (72 B, bez hw/sw verze) a **V2** (76 B) — rozlišení podle velikosti payloadu, definice `FORMAT_TELEMETRY_V1` přidána do `nastaveni.py`
- Graf průjezdu rozdělen na dvě tlačítka: **Grafy po zpracování** (bandpass filtr 1–50 Hz, detekované vrcholy, pouze ch0_int viditelný) a **Grafy — raw data** (nefiltrovaná data přímo z ADC, všechny 4 kanály viditelné); nový endpoint parametr `?raw=true`, nová funkce `get_raw_waveform_data()` v `classifier.py`
- CSS třída `.btn-outline-secondary` pro tlačítko s šedým obrysem
- Soubor `.gitignore` (vylučuje `__pycache__/`, `db/`, `data_storage/`, `*.zip`)

---

## [1.6] — 2026-06-17

### Přidáno
- Mazání záznamu průjezdu: tlačítko „Smazat" v seznamu dat zařízení, dostupné pouze uživatelům s oprávněním `can_edit` nebo vlastníkovi zařízení a administrátorovi
- Endpoint `DELETE /auth/api/message/{id}` s ověřením vlastnictví záznamu a oprávnění; smaže záznam z DB i binární soubor z disku
- Styl `.btn-outline-danger` pro červené akční tlačítko

---

## [1.5] — 2026-06-17

### Přidáno
- Docker Compose: pojmenované volumes (`vlaky_db`, `vlaky_data`) místo bind mountů — data jsou zcela oddělena od souborů aplikace a přežijí jakýkoli rebuild nebo přepsání ZIPem
- Instrukce pro nasazení (`SPUSTENI.md`) včetně postupů pro zálohování, obnovu a migraci existujících dat

### Změněno
- CSS refaktoring: odstraněny všechny `style="…"` atributy ze šablon HTML (`dashboard.html`, `device_data.html`, `layout.html`, `train_types.html`, `manage_device.html`, `devices.html`, `login.html`); přidáno ~120 nových pojmenovaných tříd do `style.css`

---

## [1.4] — 2026-06-16

### Přidáno
- Dashboard: automatický refresh karet každých 15 sekund přes endpoint `/api/dashboard`
- Globální JS funkce `formatTsCell` (datum + čas na dvou řádcích) a `formatTsFmt` (jednořádkový lidský formát) pro jednotné zobrazení časů
- Tlačítko „Reklasifikovat" u průjezdů, které již byly klasifikovány (místo „Klasifikovat")
- Automatická klasifikace vlaku ihned po dokončení příjmu posledního paketu
- Sloupec `measured_at` v tabulce `messages` — ukládá timestamp z hlavičky paketu (čas vzniku měření, ne doručení)
- Docker Compose setup s počátečními bind mounty pro `db/` a `data_storage/`

### Změněno
- Řazení průjezdů podle `COALESCE(measured_at, assigned) DESC` — primárně se používá čas měření ze zařízení
- Týdenní statistiky přepočítávány podle `measured_at` místo `assigned`
- Časová zóna aplikace nastavena na `Europe/Prague` (`TZ` v Docker Compose)
- Formát zobrazení data/času: datum a čas na dvou řádcích (`.ts-cell`), kompaktní lidský formát v telemetrii (`.ts-fmt`)
- `stat-value` zarovnána ke dnu `stat-card` pomocí flexboxu (`margin-top: auto`)
- Správa uživatelů: formuláře a záhlaví tabulky přeloženy do češtiny
- Konfigurace: `SECRET_KEY` předáván jako proměnná prostředí

### Opraveno
- Kolize MQTT paketů při současném vysílání více zařízení — přechod na `_device_session` dict pro per-device buffering
- Duplicitní definice `uloz_klasifikaci` v `data_funkce.py` způsobující chybu při volání ze `mqtt_receiver.py`

---

## [1.3] — 2026-05-29

### Přidáno
- Vizuální výstupy a dashboard s přehledem zařízení a telemetrií
- Propojení s MQTT brokerem (`iot-course-but.cloud.shiftr.io:1883`)
- Binární příjem dat ze senzorů, ukládání do `data_storage/`

_Commit: `e2ed46b` — Úprava aplikace, rozhraní výstupů, propojení mqtt_

---

## [1.2] — 2025-08-26

### Změněno
- Aktualizace `mqtt_receiver.py` — zpracování příchozích MQTT paketů

_Commit: `5df9145` — Update mqtt_receiver.py_

---

## [1.1] — 2025-08-26

### Přidáno
- Průběžné úpravy základu aplikace

_Commit: `3644af1` — chalups update pokus_

---

## [1.0] — 2025-07-02

### Přidáno
- Základ FastAPI aplikace s SQLite databází (`sqlite3`, bez ORM)
- Přihlášení a správa uživatelů
- Správa registrovaných MQTT zařízení
- Příjem a ukládání MQTT zpráv (topics `NRF/+/UP_STREAM`, `NRF/+/UP_STREAM_SYS`)
- Binární formát paketu: 7 hlavičkových polí + 4×1024 int16 vzorků + CRC
- Klasifikátor lokomotivy (bandpass filtr, `find_peaks`, Welch PSD, numpy/scipy)
- Graf signálu s přiblížením a posuvem (Chart.js + chartjs-plugin-zoom)
- Správa typů vlaků pro klasifikaci

_Commit: `db50c9f` — Základ aplikace_
