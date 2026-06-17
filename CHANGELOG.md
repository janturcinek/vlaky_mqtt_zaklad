# Changelog

Formát vychází z [Keep a Changelog](https://keepachangelog.com/cs/1.1.0/).

---

## [1.7] — 2026-06-17

### Přidáno
- Chybový log aplikace: chyby se zapisují do souboru `db/app_error.log` (rotující, max 2 MB × 3 zálohy)
- Middleware `_ErrorLoggingMiddleware` zachycuje všechny neošetřené HTTP výjimky a loguje je s traceback
- Logování MQTT chyb: selhání rozbalení paketu, chyby klasifikace
- Admin stránka `/auth/admin/error-log` — zobrazí posledních 150 záznamů, barevně odlišuje ERROR / WARNING, možnost vymazání logu
- Položka „Chybový log" v administrátorském menu

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
