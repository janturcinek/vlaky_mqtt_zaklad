# Programátorská dokumentace

## Projekt: Průjezdy vlaků — MQTT monitoring a klasifikace lokomotiv

**Verze aplikace popsaná dokumentem:** 2.7
**Datum zpracování dokumentace:** červenec 2026
**Autor dokumentu:** vygenerováno na základě analýzy zdrojového kódu projektu `vlaky_mqtt_zaklad`

---

## Obsah

1. Úvod
2. Účel a kontext aplikace
3. Technologický stack
4. Architektura aplikace
5. Struktura projektu (adresáře a soubory)
6. Konfigurace a proměnné prostředí
7. Datový model — databáze SQLite
8. Aplikační jádro (`app.py`)
9. Autentizace a autorizace
10. Příjem dat přes MQTT
11. Formát binárních paketů
12. Klasifikace lokomotiv a detekce poškození
13. Datová vrstva (`instance/data_funkce.py`)
14. Webové rozhraní a REST API — přehled endpointů
15. Frontend — šablony, styly, JavaScript
16. Logování a diagnostika
17. Nasazení a provoz (Docker)
18. Bezpečnost — analýza a známá rizika
19. Známé nedostatky a technický dluh
20. Doporučení pro další vývoj
21. Příloha A — SQL schéma databáze
22. Příloha B — Formát binárních paketů (bajt po bajtu)
23. Příloha C — Historie verzí

---

## 1. Úvod

Tento dokument popisuje interní architekturu a implementaci webové aplikace **Průjezdy vlaků**, jejímž účelem je přijímat telemetrická a měřená data z vlastních IoT senzorů umístěných u železniční tratě, tato data ukládat, automaticky z nich klasifikovat typ projíždějící lokomotivy a rychlost, detekovat možné poškození podvozku a výsledky prezentovat oprávněným uživatelům ve webovém dashboardu.

Dokument je určen vývojářům, kteří budou aplikaci dále rozvíjet, opravovat chyby nebo provádět code review. Předpokládá se základní znalost Pythonu, frameworku FastAPI, SQL a základů zpracování signálu (filtrace, FFT/PSD).

Dokument je psán jako podklad pro tvorbu formální dokumentace ve Wordu — je strukturován do číslovaných kapitol a podkapitol tak, aby šel přímo převést do formátu se stránkováním, obsahem a styly nadpisů.

---

## 2. Účel a kontext aplikace

Projekt vznikl jako řešení pro monitoring průjezdů vlaků pomocí vlastních senzorových jednotek (dále „zařízení“ nebo „unit“), které jsou instalovány u kolejí a měří elektrický signál vyvolaný průjezdem kol lokomotivy (indukční/proudová smyčka). Zařízení komunikují přes mobilní síť s MQTT brokerem třetí strany (`shiftr.io`) a odesílají:

- **datové pakety** s naměřeným časovým průběhem signálu (4 kanály, 1024 vzorků na kanál a paket, více paketů na jeden průjezd),
- **telemetrické (SYS) pakety** s informacemi o stavu jednotky — teplota, vlhkost, tlak, napětí baterie, síla signálu, uptime, GPS.

Aplikace tato data přijímá na pozadí (samostatné vlákno s MQTT klientem), ukládá je do SQLite databáze a na disk, a z naměřeného signálu automaticky určuje:

- **typ lokomotivy** (na základě databáze known-vzorů typů vlaků a časování detekovaných průjezdů náprav),
- **rychlost** v km/h,
- **poškození podvozku** (na základě spektrální analýzy vibrací).

Výsledky jsou zobrazeny ve webovém dashboardu s možností správy zařízení, uživatelů, přístupových práv a databáze typů vlaků použité ke klasifikaci.

---

## 3. Technologický stack

| Vrstva | Technologie | Verze (dle `requirements.txt`) |
|---|---|---|
| Webový framework | FastAPI | 0.136.1 |
| ASGI server | Uvicorn (`[standard]`) | 0.47.0 |
| Upload formulářů | python-multipart | 0.0.29 |
| Šablonovací systém | Jinja2 (přes `fastapi.templating`) | 3.1.6 |
| Session cookies | Starlette `SessionMiddleware` + itsdangerous | 2.2.0 |
| Hashování hesel | Werkzeug (`generate_password_hash`/`check_password_hash`) | 3.1.8 |
| MQTT klient | paho-mqtt | 2.1.0 |
| Numerické výpočty | NumPy | 2.4.6 |
| Zpracování signálu | SciPy (`scipy.signal`) | 1.17.1 |
| Databáze | SQLite (přes standardní `sqlite3`, bez ORM) | — |
| Frontend | Bootstrap (CSS/JS, lokální kopie), vlastní `style.css`, vanilla JS | — |
| Grafy | Chart.js 4.4.0 + `chartjs-plugin-zoom` + Hammer.js (načítány z CDN) | — |
| Kontejnerizace | Docker (multi-stage build), Docker Compose | — |
| Běhové prostředí | Python 3.12 (`python:3.12-slim`) | — |

Aplikace **nepoužívá žádný ORM** (SQLAlchemy apod.) — veškerý přístup k datům je přes parametrizované SQL dotazy v modulu `instance/data_funkce.py`. Nepoužívá se žádný migrační nástroj (Alembic apod.); jednoduché schema migrace (přidání sloupců) se řeší ručně v `init_db()` pomocí `PRAGMA table_info` a `ALTER TABLE`.

---

## 4. Architektura aplikace

Aplikace běží jako jediný Python proces se dvěma souběžně běžícími smyčkami:

1. **ASGI webový server (Uvicorn/FastAPI)** — obsluhuje HTTP požadavky (webové rozhraní, REST/JSON API pro AJAX volání z frontendu).
2. **MQTT přijímací vlákno** (`threading.Thread(target=run_mqtt_receiver, daemon=True)`, spuštěné v `create_app()`) — udržuje trvalé spojení s MQTT brokerem a synchronně zpracovává příchozí zprávy v callbacku `on_message`.

Obě smyčky sdílejí stejnou SQLite databázi (soubor `db/vlaky.db`) a stejný souborový systém pro binární data (`data_storage/`). Mezi vlákny navíc existuje sdílený in-memory stav (moduly `mqtt_receiver.py`):

- `packet_buffers` — rozpracované (dosud nekompletní) přenosy dat, klíčované `(device_id, device_timestamp)`,
- `buffer_timestamps` — čas posledního přijatého paketu v daném bufferu (pro detekci timeoutu),
- `recent_messages` — kruhový buffer posledních 50 MQTT zpráv pro živý log v adminském dashboardu,
- `device_alive` — poslední heartbeat (`UNIT ALIVE`) každého zařízení.

Tento stav **není perzistentní** — při restartu aplikace se ztrácí (rozpracované přenosy, které v tu chvíli nebyly dokončené, zůstanou jako fragmenty bez uložení, pokud restart nastane před vypršením `BUFFER_TIMEOUT_SECONDS`).

### 4.1 Vysokoúrovňový diagram toku dat

```
 IoT senzor (NRF unit)
        │  MQTT publish (binární payload)
        ▼
 MQTT broker (shiftr.io, port 1883)
        │  subscribe: NRF/+/UP_STREAM, NRF/+/UP_STREAM_SYS
        ▼
 mqtt_receiver.py :: on_message()
        │
        ├─ UP_STREAM_SYS ─► on_sys_message() ─► data_funkce.uloz_podmínky() ─► tabulka device_conditions
        │
        └─ UP_STREAM ─► struct.unpack ─► packet_buffers[(device_id, ts)]
                              │
                              ├─ neúplné + timeout ─► uložení jako *_incomplete.bin, is_complete=0
                              │
                              └─ kompletní ─► spojení paketů do .bin souboru (data_storage/{device_id}/)
                                              │
                                              ├─ data_funkce.uloz_zpravu() ─► tabulka messages
                                              │
                                              └─ classifier.classify_bin_file() ─► data_funkce.uloz_klasifikaci()

 Webový uživatel
        │ HTTP
        ▼
 FastAPI routery (auth_router, device_router, admin_router)
        │
        ▼
 instance/data_funkce.py  ◄──────────────────────────────► SQLite (db/vlaky.db)
        │
        ▼
 Jinja2 šablony (templates/) ─► HTML + Chart.js grafy z .bin souborů (přes classifier.get_waveform_data)
```

### 4.2 Middleware a request pipeline

`create_app()` v `app.py` registruje middleware v tomto pořadí:

1. `SessionMiddleware` (starlette) — podepisuje session cookie klíčem `DevelopmentConfig.SECRET_KEY`.
2. `_ErrorLoggingMiddleware` (vlastní, `BaseHTTPMiddleware`) — obaluje `call_next`, zachytává jakoukoli neošetřenou výjimku, zaloguje ji (`app_logger.get_logger().error(...)` s celým tracebackem) a znovu ji vyhodí (`raise`), takže FastAPI ji dál zpracuje standardním způsobem (500).

Dále jsou registrovány dva exception handlery:

- `NotAuthenticatedException` → `RedirectResponse("/auth/login", 302)`
- `NotAuthorizedException` → `RedirectResponse("/auth/dashboard", 302)` — uživatel JE přihlášen, jen mu chybí role; **od v2.7** proto míří na vlastní dashboard, ne na login (dřív mířil na login stejně jako nepřihlášený uživatel, což u již přihlášeného vypadalo jako neočekávané odhlášení). `ma_roli()` (kap. 9.2) navíc před vyhozením výjimky nastaví vysvětlující flash zprávu.

---

## 5. Struktura projektu (adresáře a soubory)

```
vlaky_mqtt_zaklad/
├── app.py                     # Vstupní bod aplikace, factory create_app()
├── nastaveni.py                # Konfigurace, konstanty, binární formáty paketů
├── app_logger.py                # Rotující chybový log (db/app_error.log)
├── mqtt_log.py                 # Denní textový log MQTT událostí (db/mqtt_logs/)
├── mqtt_receiver.py             # MQTT klient, buffering paketů, telemetrie
├── classifier.py                # Klasifikace vlaků ze signálu (SciPy/NumPy)
├── decorators.py                # FastAPI dependency funkce pro auth (require_login, ma_roli)
├── helpers.py                   # Flash zprávy, Jinja2Templates, template_context()
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── CHANGELOG.md
├── SPUSTENI.md                  # Provozní příručka pro nasazení (Docker)
│
├── auth/
│   ├── __init__.py
│   ├── models.py                # User model, load_user(), load_labels() (i18n)
│   ├── routes.py                 # /auth/login, /auth/logout, správa uživatelů a rolí
│   ├── devices.py                # Dashboard, zařízení, data zařízení, waveform API, typy vlaků
│   └── admin.py                  # Chybový log a MQTT log (admin sekce)
│
├── instance/
│   ├── data_funkce.py            # Veškerá práce s databází (bez ORM, raw SQL)
│   └── langs.json                # Slovník textových popisků (cz/eng)
│
├── templates/                    # Jinja2 šablony (viz kap. 15)
│   ├── layout.html
│   ├── nav_bar.html
│   ├── login.html
│   ├── dashboard.html
│   ├── devices.html
│   ├── manage_device.html
│   ├── device_data.html
│   ├── train_types.html
│   ├── users.html
│   ├── user_detail.html
│   ├── error_log.html
│   ├── mqtt_log_list.html
│   └── mqtt_log_detail.html
│
├── static/
│   ├── bootstrap.min.css / .js
│   └── style.css
│
├── db/                            # RUNTIME — SQLite DB + logy (mimo git, viz .gitignore)
│   ├── vlaky.db
│   ├── app_error.log
│   └── mqtt_logs/YYYY-MM-DD.log
│
└── data_storage/                  # RUNTIME — binární soubory naměřených průjezdů (mimo git)
    └── {device_id}/{timestamp}.bin
```

Soubory `db/` a `data_storage/` jsou vyloučeny z gitu (`.gitignore`) a v Dockeru jsou mapované jako bind mounty na hostitelský disk — přežijí rebuild image i přepsání zdrojových souborů novou verzí.

---

## 6. Konfigurace a proměnné prostředí

Veškerá konfigurace je soustředěna v `nastaveni.py`, třída `DevelopmentConfig`:

| Proměnná prostředí | Výchozí hodnota | Účel |
|---|---|---|
| `SECRET_KEY` | `'tajny_klic_zmente_v_produkci'` | Podpisový klíč session cookie (Starlette `SessionMiddleware`). **Musí být změněn v produkci** — viz kap. 18. |
| `DATABASE_PATH` | `<root>/db/vlaky.db` | Cesta k SQLite souboru. |

Další konstanty v `nastaveni.py` (nejsou konfigurovatelné přes prostředí, vyžadují úpravu zdrojového kódu):

| Konstanta | Hodnota | Význam |
|---|---|---|
| `APP_VERSION` | `"2.7"` | Zobrazuje se v patičce/topbaru aplikace, ručně aktualizováno při vydání. |
| `BUFFER_TIMEOUT_SECONDS` | `30` | Maximální nečinnost (v sekundách) mezi dvěma pakety jednoho přenosu, po jejímž překročení se buffer uzavře jako neúplný. |
| `WAVE_SAMPLE_LEN` | `1024` | Počet vzorků na kanál v jednom datovém paketu. |
| `format_str` | `'<HHHHIIH1024h1024h1024h1024hH'` | `struct` formát datového paketu (7 hlavičkových polí + 4×1024 vzorků int16 + CRC). |
| `FORMAT_TELEMETRY_V1` / `FORMAT_TELEMETRY_V2` | viz kap. 11 | `struct` formáty telemetrických SYS paketů. |

V Docker Compose (`docker-compose.yml`) se `SECRET_KEY` a `TZ` nastavují jako proměnné prostředí kontejneru; `DATABASE_PATH` se v produkčním nasazení nepřepisuje (výchozí cesta uvnitř kontejneru `/app/db/vlaky.db` mapovaná na bind mount `./db`).

MQTT přístupové údaje (broker, uživatelské jméno, heslo) jsou **napevno zapsané ve zdrojovém kódu** v `mqtt_receiver.py::run_mqtt_receiver()` — nejsou konfigurovatelné přes prostředí (viz kap. 18/19).

---

## 7. Datový model — databáze SQLite

Databáze je inicializována funkcí `init_db()` (`instance/data_funkce.py`), která je bezpečné volat opakovaně (všechny `CREATE TABLE` používají `IF NOT EXISTS`, seed data `INSERT OR IGNORE`). Volá se při každém startu aplikace v `create_app()`.

### 7.1 Přehled tabulek

| Tabulka | Účel | Klíčové vazby |
|---|---|---|
| `users` | Uživatelské účty | — |
| `user_passwords` | Historie hashů hesel (kontroluje se vždy poslední záznam dle `created`) | `user_id` → `users` |
| `system_roles` | Číselník rolí (seedováno: `admin`, `user`) | — |
| `user_roles` | Přiřazení rolí uživatelům, se soft-delete (`removed`) | `user_id` → `users`, `role_id` → `system_roles` |
| `devices` | Registrovaná IoT zařízení (senzory) | `user_id` → `users` (vlastník) |
| `messages` | Jeden záznam = jeden přijatý/uložený průjezd (i neúplný) | `device_id` → `devices` |
| `mqtt_packets` | Pomocná tabulka pro logování jednotlivých paketů (viz pozn. níže) | — |
| `device_conditions` | Historie telemetrie zařízení (teplota, vlhkost, baterie…) | `device_id` → `devices` |
| `device_access` | ACL — sdílený přístup k zařízení jiným uživatelům než vlastníkovi | `device_id` → `devices`, `user_id` → `users` |
| `train_types` | Databáze known-vzorů typů lokomotiv pro klasifikaci; seedována z `nastaveni.TRAIN_TYPES_SEED` | — |

> **Poznámka:** tabulka `mqtt_packets` se fakticky neplní — funkce `save_packet_to_db()`, která do ní dřív zapisovala, byla nikdy nevolaná a byla odstraněna ve v2.7 (podrobná evidence jednotlivých MQTT paketů je nahrazena novějším denním textovým logem `mqtt_log.py`, viz kap. 16). Samotná tabulka v schématu zůstává (neškodná, jen prázdná) — viz kap. 19. Kompletní DDL viz Příloha A.

### 7.2 Entitně-relační přehled

```
users 1───* user_roles *───1 system_roles
users 1───* user_passwords
users 1───* devices (vlastník)
users 1───* device_access *───1 devices  (sdílený přístup)
devices 1───* messages
devices 1───* device_conditions
messages (train_type, speed_kmh, damage_detected) ← vyplňuje classifier.py
train_types  (samostatná, referenční tabulka bez FK — čtena klasifikátorem)
```

### 7.3 Tabulka `messages` — klíčový záznam aplikace

Nejdůležitější tabulka z pohledu byznys logiky — jeden řádek reprezentuje jeden přijatý/zpracovaný průjezd vlaku:

| Sloupec | Typ | Popis |
|---|---|---|
| `message_id` | INTEGER PK | |
| `device_id` | INTEGER FK | Zařízení, které záznam vytvořilo |
| `assigned` | TEXT | Čas vložení do DB (server, UTC — `CURRENT_TIMESTAMP`) |
| `measured_at` | TEXT | Čas měření dle hlavičky paketu (lokální, ze zařízení) — **preferovaný pro zobrazení a řazení** |
| `topic` | TEXT | MQTT topic, ze kterého data přišla |
| `packets` | INTEGER | Počet přijatých paketů |
| `filename` | TEXT UNIQUE | Cesta k `.bin` souboru na disku |
| `train_type` | TEXT | Výsledek klasifikace (viz kap. 12) |
| `speed_kmh` | REAL | Odhadovaná rychlost |
| `damage_detected` | INTEGER (0/1) | Příznak detekovaného poškození podvozku |
| `classified_at` | TEXT | Čas poslední (re)klasifikace |
| `is_complete` | INTEGER (0/1), default 1 | 0 = přenos skončil timeoutem s chybějícími pakety (viz kap. 10.3) |

Sloupce `measured_at` a `is_complete` byly do schématu doplněny dodatečně (verze 1.4 a 1.9) a jsou zajištěny idempotentní migrací v `init_db()` přes `PRAGMA table_info` + `ALTER TABLE ... ADD COLUMN`.

---

## 8. Aplikační jádro (`app.py`)

Funkce `create_app()`:

1. Vytvoří instanci `FastAPI()`.
2. Zaregistruje middleware (session, error logging) — viz kap. 4.2.
3. Namountuje statické soubory na `/static` (adresář `static/` relativně k umístění `app.py`).
4. Zaregistruje tři routery: `auth_router`, `device_router`, `admin_router` (všechny s prefixem `/auth`, resp. `/auth/admin`).
5. Zaregistruje exception handlery pro autentizaci/autorizaci.
6. Definuje endpoint `GET /` — přesměrování na `/auth/dashboard` (přihlášen) nebo `/auth/login` (nepřihlášen).
7. Definuje endpoint `GET /add-user` — jednorázové vytvoření výchozího admin účtu (login `admin`, heslo `admin123`). **Od verze 2.6** se sám natrvalo uzamkne, jakmile v DB existuje alespoň jeden uživatel — do té doby je bez autentizace/autorizace dostupný komukoli, viz kap. 18, bod 1.
8. Spustí MQTT vlákno (`run_mqtt_receiver`, daemon thread).
9. Zavolá `init_db()`.
10. Vrátí instanci `app`.

Modul na úrovni importu rovnou vytváří globální proměnnou `app = create_app()` — to znamená, že **MQTT vlákno se spustí a databáze se inicializuje při každém importu modulu `app`**, tedy i např. při spuštění nástrojů jako `pytest` nebo interaktivním `import app` (viz kap. 19 — chybí oddělení pro testovací prostředí).

Spuštění v `__main__` používá port `5000` (`uvicorn.run("app:app", host="0.0.0.0", port=5000)`), zatímco `Dockerfile` spouští `uvicorn app:app --host 0.0.0.0 --port 8000` — v obou případech jde o odlišné porty, sladěné až v `docker-compose.yml` mapováním `127.0.0.1:5000:8000`.

---

## 9. Autentizace a autorizace

### 9.1 Princip

Autentizace je založena na **podepsané session cookie** (Starlette `SessionMiddleware`, algoritmus/podpis přes `itsdangerous`, klíč `SECRET_KEY`). Po úspěšném loginu (`POST /auth/login`) se do session uloží `user_id` a `login`. Session **neobsahuje** informaci o roli — ta se dotahuje z DB při každém požadavku.

Hesla se ukládají hashovaná pomocí `werkzeug.security.generate_password_hash` do tabulky `user_passwords`. Historie hashů se zachovává (nový řádek při každé změně hesla), ale **ověřuje se vždy jen nejnovější záznam** (`ORDER BY created DESC LIMIT 1`) — staré hashe se fakticky nikdy nemažou ani nepoužívají, jde tedy o rostoucí, nevyužívanou historii.

### 9.2 FastAPI dependency injection (`decorators.py`)

| Funkce | Použití | Chování |
|---|---|---|
| `get_current_user(request)` | Pomocná, nevyhazuje výjimku | Vrátí `User` nebo `None` |
| `require_login(request)` | `Depends(require_login)` | Vyhodí `NotAuthenticatedException`, pokud není přihlášen; jinak vrátí `User` |
| `ma_roli(role: str)` | `Depends(ma_roli("admin"))` — dependency factory | Vyhodí `NotAuthenticatedException` (nepřihlášen) nebo `NotAuthorizedException` (nemá roli); jinak vrátí `User` |

Oba výjimkové typy jsou globálně zachyceny v `app.py` a převedeny na `302 → /auth/login` (viz kap. 4.2).

### 9.3 Vynucování rolí (sjednoceno ve v2.7)

Do verze 2.6 existovaly v kódu **dva různé způsoby**, jak endpoint vynucuje, že uživatel musí být administrátor: deklarativně přes `Depends(ma_roli("admin"))` (např. `/auth/users`), nebo ručně uvnitř těla funkce (`if not current_user.admin: ...`) u `train-types` a `admin/*` endpointů.

**Od verze 2.7** je to sjednocené — všech 10 dříve ručně kontrolovaných endpointů (`/auth/train-types*` ×5, `/auth/admin/*` ×4, a implicitně i mrtvá `_require_admin()`, která byla při té příležitosti odstraněna) nyní používá výhradně `Depends(ma_roli("admin"))`. Aby sjednocení nezhoršilo UX, byly zároveň upraveny dvě navazující věci:

- `ma_roli()` (`decorators.py`) nastaví před vyhozením `NotAuthorizedException` obecnou flash zprávu (`f"K této akci nemáte dostatečné oprávnění (vyžaduje roli „{role}“)."`) — dřív flash zprávu mělo jen ruční ošetření na `train_types_get`, zbytek endpointů přesměrovával tiše.
- Globální handler `NotAuthorizedException` přesměrovává na `/auth/dashboard` místo `/auth/login` (viz kap. 4.2).

### 9.4 Model `User` (`auth/models.py`)

```python
class User:
    def __init__(self, user_id, login, name, surname, admin=False):
        ...
        if not admin:
            admin = data_funkce.ma_roli(user_id, "admin")
        self.admin = admin
```

`User.admin` se dopočítává dotazem do DB při každém vytvoření instance (tedy prakticky při každém požadavku, protože `load_user()` je volané z `require_login`/`ma_roli` bez cachování mezi requesty).

### 9.5 Autorizace na úrovni zařízení (ACL)

Zařízení (`devices`) mají vlastníka (`devices.user_id`). Kromě toho existuje tabulka `device_access`, která umožňuje přiřadit **čtecí** (výchozí) nebo **čtecí+editační** (`can_edit=1`) přístup libovolnému dalšímu uživateli.

Pomocné funkce v `data_funkce.py`:

| Funkce | Vrací `True`, pokud… |
|---|---|
| `ma_pristup_k_zarizeni(device_id, user_id, is_admin)` | uživatel je admin, vlastník, nebo má záznam v `device_access` (libovolný `can_edit`) |
| `muze_editovat_zarizeni(device_id, user_id, is_admin)` | uživatel je admin, vlastník, nebo má `device_access.can_edit = 1` |

Administrátor má vždy plný přístup ke všem zařízením bez ohledu na `device_access`.

### 9.6 Rate-limiting přihlášení (od verze 2.6)

`POST /auth/login` (`auth/routes.py`) je chráněno jednoduchým in-memory limiterem proti opakovanému hádání hesla:

```python
_LOGIN_ATTEMPTS: dict[str, dict] = {}
_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 60
```

Klíčem je zadané přihlašovací jméno (`login_name`), ne IP adresa. Po `_MAX_ATTEMPTS` (5) neúspěšných pokusech v řadě na stejné jméno se toto jméno na `_LOCKOUT_SECONDS` (60 s) uzamkne — další pokus vrátí flash zprávu s odpočtem, aniž by se vůbec ověřovalo heslo proti DB. Úspěšné přihlášení záznam pro dané jméno smaže (`_login_register_success`).

Jde o stav **v paměti procesu**, stejného charakteru jako `packet_buffers` v `mqtt_receiver.py` (kap. 4.1) — platí tedy stejná omezení: nepersistuje restart aplikace a nesdílí se mezi více worker procesy, pokud by byl Uvicorn v budoucnu spuštěn s `--workers > 1`. Pro nasazení s více workery by bylo nutné přesunout stav do sdíleného úložiště (Redis apod.).

---

## 10. Příjem dat přes MQTT (`mqtt_receiver.py`)

### 10.1 Připojení k brokeru

```python
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "FastAPI_MQTT_Receiver")
client.username_pw_set("iot-course-but", "thisisthemostsecretsecretever")
client.connect("iot-course-but.cloud.shiftr.io", 1883)
client.subscribe("NRF/+/UP_STREAM")
client.subscribe("NRF/+/UP_STREAM_SYS")
client.loop_forever()
```

Broker je sdílená veřejná instance `shiftr.io` (kurzovní/výukové prostředí BUT), port **1883 bez TLS**. Přihlašovací údaje jsou napevno v kódu (viz kap. 18). Topic schéma: `NRF/{client_id}/UP_STREAM` (data) a `NRF/{client_id}/UP_STREAM_SYS` (telemetrie), kde `client_id` je identifikátor konkrétní jednotky odpovídající `devices.client_id` v DB.

### 10.2 Zpracování datového paketu — `on_message()`

Pro každou příchozí zprávu na topicu `UP_STREAM`:

1. Zavolá se `_cleanup_stale_buffers()` (viz 10.3).
2. Payload se rozbalí pomocí `struct.unpack(format_str, msg.payload)` → `DataPacket`. Chyba rozbalení (nesprávná délka payloadu apod.) se zaloguje (`app_logger` + `mqtt_log.log_event("PARSE_ERR", …)`) a zpráva se zahodí.
3. `client_id` (druhý segment topicu) se ověří přes `data_funkce.registerovano(client_id)`. Není-li zařízení registrované, zpráva se zahodí a zaloguje se `REJECTED` událost — **data z neregistrovaných zařízení se nikam neukládají**, jsou vidět jen v živém logu na dashboardu, odkud je lze rovnou „Registrovat“ (odkaz předvyplní Client ID ve formuláři přidání zařízení).
4. Session klíč `key = (device_id, device_ts)`, kde `device_ts = packet.timestamp` (unixový čas z hlavičky paketu, případně čas serveru, pokud je `timestamp <= 0`). Klíčování dvojicí umožňuje **souběžné zpracování více přenosů** od stejného i různých zařízení.
5. Paket se uloží do `packet_buffers[key][packet.actual_packet_nr] = payload` (přepis při duplicitě, ne přidání).
6. `buffer_timestamps[key]` se aktualizuje při **každém** přijatém paketu daného bufferu — timeout tedy měří **mezeru mezi pakety**, ne celkovou dobu přenosu (oprava v. 2.4 — pomalý, ale kontinuální přenos více paketů nevyprší předčasně).
7. Jakmile `len(packet_buffers[key]) == packet.total_packet_nr`, pakety se seřadí podle pořadového čísla, spojí do jednoho binárního bloku a uloží na disk (`data_storage/{device_id}/{ts}.bin`), vytvoří se řádek v `messages` (`uloz_zpravu`), zaloguje se `COMPLETE` událost a **ihned se spustí automatická klasifikace** (`classifier.classify_bin_file`), jejíž výsledek se zapíše zpět do `messages` (`uloz_klasifikaci`). Buffer se pak z paměti odstraní.

### 10.3 Timeout a ukládání neúplných přenosů

`_cleanup_stale_buffers()` se volá na začátku každého `on_message()` (tedy efektivně při každé nové příchozí zprávě, ne na časovači) a pro každý buffer, kde od posledního paketu uplynulo více než `BUFFER_TIMEOUT_SECONDS` (30 s):

- pokud buffer neobsahuje žádný paket, je jen zahozen,
- jinak se dostupné pakety seřadí a spojí, uloží se jako `..._incomplete.bin`, a vytvoří se záznam v `messages` s `is_complete=False` (zaloguje se `INCOMPLETE`). **Neúplné přenosy se tedy neztrácejí**, ale ani se u nich nespouští automatická klasifikace (klasifikace proběhne až po ručním kliknutí na „Klasifikovat“ ve webovém rozhraní, kde na krátký/poškozený signál klasifikátor reaguje výsledkem `"neurčen"`).

Vzhledem k tomu, že cleanup běží jen jako vedlejší efekt přijetí nové zprávy (ne jako samostatné periodické vlákno/timer), buffer po posledním paketu **zůstane „zaseknutý“ v paměti až do příští libovolné MQTT zprávy** (od kteréhokoli zařízení) — v provozu s pravidelným provozem (heartbeaty `UNIT ALIVE` po celé topologii) to prakticky není problém, ale je to architektonická slabina, kterou má smysl znát.

### 10.4 Telemetrie — `on_sys_message()`

Zprávy na topicu `UP_STREAM_SYS` mají dvě podoby:

1. **Heartbeat** — payload doslova `b"UNIT ALIVE"`. Aktualizuje `device_alive[device_id]` (ISO timestamp), který dashboard využívá pro zelenou/šedou tečku „online“ indikátoru (zelená < 10 min stáří, jinak šedá; obnovuje se na frontendu každých 15 s přes `/auth/api/dashboard`).
2. **Binární telemetrický paket** — rozlišení formátu **V1 vs. V2 podle délky payloadu** (V1 = 72 B, V2 = 76 B; V2 přidává `hw_ver`/`sw_ver` pole). Po rozbalení se extrahují teplota, vlhkost, tlak, napětí baterie, síla signálu a uptime a uloží se do `device_conditions` (`data_funkce.uloz_podmínky`). Pole `train_counter` v telemetrii se **nebere z paketu**, ale dopočítává live dotazem `dej_pocet_zprav_zarizeni()` (počet řádků v `messages` pro dané zařízení) — telemetrický paket ho tedy jen doprovodně reportuje z pohledu firmwaru, ale server si ho počítá nezávisle.

### 10.5 Živé a perzistentní logování

- `recent_messages` (deque, max 50) — in-memory, dostupné přes `GET /auth/api/mqtt-log`, vykreslované na dashboardu (polling každé 3 s, jen pro adminy).
- `mqtt_log.log_event(event_type, **kwargs)` (od verze 2.1) — zapisuje řádek do `db/mqtt_logs/YYYY-MM-DD.log` (nový soubor každý den). Typy událostí: `COMPLETE`, `INCOMPLETE`, `REJECTED`, `PARSE_ERR`, `CLASSIFY_ERR`. Prohlížení přes `/auth/admin/mqtt-log` (seznam dnů) a `/auth/admin/mqtt-log/{soubor}` (detail, read-only, bez možnosti mazání).

---

## 11. Formát binárních paketů

### 11.1 Datový paket (`format_str`)

```
'<HHHHIIH' + '1024h'*4 + 'H'
```

| Pole | Typ | Bajtů | Popis |
|---|---|---|---|
| `packet_header` | H (uint16) | 2 | Hlavička/magic |
| `packet_version` | H | 2 | Verze formátu paketu |
| `actual_packet_nr` | H | 2 | Pořadové číslo paketu (od 1) |
| `total_packet_nr` | H | 2 | Celkový počet paketů v přenosu |
| `timestamp` | I (uint32) | 4 | Unix timestamp měření (ze zařízení) |
| `total_sample_count` | I | 4 | Celkový počet vzorků měření |
| `train_counter` | H | 2 | Interní počítadlo průjezdů na jednotce |
| `chan_0_vlt[1024]` | h (int16) ×1024 | 2048 | Kanál 0 — napětí |
| `chan_0_int[1024]` | h ×1024 | 2048 | Kanál 0 — integrál (hlavní signál pro klasifikaci) |
| `chan_1_vlt[1024]` | h ×1024 | 2048 | Kanál 1 — napětí |
| `chan_1_int[1024]` | h ×1024 | 2048 | Kanál 1 — integrál |
| `CRC` | H | 2 | Kontrolní součet |

**Celková velikost jednoho paketu: 8 212 bajtů** (18 B hlavička + 8 192 B vzorky + 2 B CRC).

Vzorkovací frekvence je v `classifier.py` napevno definovaná konstantou `FS = 2000.0` Hz — **není součástí paketu**, musí odpovídat skutečné konfiguraci firmwaru senzoru.

### 11.2 Telemetrický paket (SYS) — V1 / V2

Rozlišení dle velikosti payloadu: V1 = 72 B, V2 = 76 B (V2 = V1 + 4 bajty `hw_ver_major/minor`, `sw_ver_major/minor` navíc hned za `packet_ver_minor`). Kompletní výčet polí obou formátů viz `nastaveni.py` (`FORMAT_TELEMETRY_V1`, `FORMAT_TELEMETRY_V2`) a Příloha B. Z aplikačního pohledu se reálně využívají jen pole: `packet_ver_major/minor`, `unit_temperature`, `unit_humidity`, `unit_pressure`, `batt_voltage`, `signal_strength`, `uptime_minutes` (GPS, IMEI, modem stavová slova apod. se přijímají, ale dále v aplikaci nepoužívají ani neukládají).

---

## 12. Klasifikace lokomotiv a detekce poškození (`classifier.py`)

Modul vznikl adaptací z prototypového Jupyter notebooku (`klasifikace.ipynb`, zmíněno v docstringu) pro přímou práci s uloženými `.bin` soubory, bez závislosti na pandas (vlastní `_isna`/`_notna` náhrady za `pd.isna`).

### 12.1 Vstup a předzpracování

`load_bin_channels()` načte `.bin` soubor (posloupnost konkatenovaných datových paketů), rozparsuje je stejným `format_str` jako přijímač a poskládá 4 kanály jako `numpy` pole typu `float`. Hlavní signál pro klasifikaci je `chan_0_int`.

`classify_bin_file()`:

1. Pokud je záznam kratší než `cut_samples` (výchozí 300 vzorků ≈ 0,15 s), vrátí `typ_vlaku = "neurčen"` s chybovou poznámkou „příliš krátký záznam“.
2. Aplikuje **Butterworth pásmovou propust** (`butter`, řád 4, 1–50 Hz) na celý signál pomocí `filtfilt` (zero-phase — nezpůsobuje fázový posun), poté ořízne prvních `cut_samples` vzorků (odstranění přechodového/okrajového jevu filtru a případného náběhu senzoru).

### 12.2 Detekce průjezdů náprav (peak detection)

Na invertovaném filtrovaném signálu (`-x_hp`) se hledají vrcholy pomocí `scipy.signal.find_peaks` s parametry `height=170` (výchozí práh) a minimální rozestup `min_distance_s=0.05 s` (100 vzorků při 2 kHz). Každý vrchol odpovídá průjezdu jedné nápravy/dvojkolí nad senzorem.

Z prvních čtyř detekovaných vrcholů se spočítají časové rozestupy:

```
dt12 = t[1] - t[0]
dt23 = t[2] - t[1]
dt34 = t[3] - t[2]
loco_ratio = dt23 / dt12
```

### 12.3 Rozhodovací logika `_classify_locomotive()`

- Pokud `loco_ratio` odpovídá symetrickému uspořádání podvozku (`0.85 ≤ ratio ≤ 1.15`, tzv. „CoCo“ heuristika), použije se průměr `(dt12+dt23)/2` jako reprezentativní čas mezi nápravami; jinak (typicky asymetrický Bo'Bo' podvozek) se použije `(dt12+dt34)/2`, případně jen `dt12`.
- Pro každý záznam v databázi typů vlaků (`train_types`, viz kap. 12.5) se spočítá odhadovaná rychlost `(rozvor_m / prumerny_cas) * 3.6` a porovná se naměřený poměr `loco_ratio` s referenčním `pomer` daného typu.
- Vybere se typ s **nejmenší odchylkou poměru**, který zároveň implikuje rychlost `≤ 170 km/h` (fyzikální plausibilita/odfiltrování chybných detekcí) a jehož odchylka je uvnitř tolerance `max(0.15, pomer * 0.06)` (relativní tolerance roste s velikostí poměru).
- Nenajde-li se žádná shoda v toleranci, výsledek je `"neurčen"`.

Rychlost (`_calculate_speed`) se dopočítává stejným vzorcem pro již určený typ; pokud typ je `"neurčen"` nebo `"chyba_měření"`, rychlost je `None`.

### 12.4 Detekce poškození podvozku (PSD)

Na kanálu `chan_0_vlt` (napětí, ne integrál), po odečtení stejnosměrné složky, se spočítá výkonové spektrum pomocí Welchovy metody (`scipy.signal.welch`, `nperseg=1024`). Průměrný výkon v pásmu **75–100 Hz** se porovná s empirickým prahem **1000** — překročení je interpretováno jako `poskozeni_podvozku = True` (typický spektrální projev vady na obvodu kola — ploška/flat spot). Práh ani frekvenční pásmo nejsou v UI konfigurovatelné, jsou napevno v kódu.

### 12.5 Detekce chyby měření

Pokud první detekovaný vrchol nastane příliš brzy (`< 0,524 s` od začátku ořízlého signálu), výsledek klasifikace je natvrdo `"chyba_měření"` (typicky useknutý/torzo signál na začátku přenosu — např. při ztrátě prvních paketů) a rychlost se nepočítá.

### 12.6 Databáze typů vlaků (`train_types`)

Klasifikátor čte referenční databázi typů primárně z SQLite (`data_funkce.dej_train_db_pro_klasifikaci()`); pokud je nedostupná (chyba připojení), použije se fallback `_TRAIN_DB_FALLBACK` přímo v `classifier.py` (bez možnosti úprav administrátorem — pouze záložní řešení pro degradovaný provoz). **Od verze 2.7** je `_TRAIN_DB_FALLBACK` jen alias na `nastaveni.TRAIN_TYPES_SEED` — stejná konstanta, kterou `init_db()` používá i pro počáteční seed tabulky `train_types`, takže data existují v kódu jen na jednom místě (dřív byla duplicitně definována zvlášť v `data_funkce.py` a zvlášť v `classifier.py`).

Databáze je editovatelná administrátorem přes `/auth/train-types` (přidání/úprava/smazání typu — `typ`, `pomer`, `dvojkoli_mm`, volitelný `popis`). Doporučený postup zjištění `pomer` pro nový typ vlaku je popsán v uživatelské příručce — v praxi jde o zprůměrování `loco_ratio` z několika reálných průjezdů daného vlaku.

### 12.7 Data pro grafy

`get_waveform_data()` vrací decimovaná (max. 5000 bodů), **filtrovaná** data všech 4 kanálů + časy detekovaných vrcholů — použito pro tlačítko „Grafy po zpracování“. `get_raw_waveform_data()` vrací **nefiltrovaná** syrová data přímo z ADC — použito pro „Grafy — raw data“. Obě funkce jsou volané přes JSON endpoint `GET /auth/api/message/{id}/waveform` (parametr `?raw=true/false`).

---

## 13. Datová vrstva (`instance/data_funkce.py`)

Jde o jediný modul soustřeďující veškerý přístup k databázi — cca 1000 řádků, žádné třídy, čisté funkce nad `sqlite3.connect()` (nové připojení při každém volání, `conn.row_factory = sqlite3.Row` u novějších funkcí umožňuje přístup podle jména sloupce; starší funkce (z verze 1.0) vrací nepojmenované n-tice a přistupuje se k nim indexy — nekonzistence stylu napříč souborem, patrná i v šablonách, kde se místy přistupuje k datům jako `dev[1]`, jinde jako `z.client_id`).

### 13.1 Kategorie funkcí

| Kategorie | Příklady funkcí |
|---|---|
| Inicializace DB | `get_db_connection`, `init_db` |
| Uživatelé a hesla | `is_user`, `pass_ok`, `uloz_uzivatele`, `zmen_uzivatele`, `zmen_heslo`, `login_check`, `seznam_uzivatelu`, `dej_detail_uzivatele` |
| Role | `seznam_roli`, `pocet_adminu`, `pridej_roli`, `odeber_roli`, `dej_user_role_detail`, `ma_roli` |
| Zařízení | `dej_seznam_zarizeni(_pro_uzivatele)`, `dej_zarizeni`, `pridej_zarizeni`, `uprav_zarizeni`, `dej_pocet_zarizeni`, `registerovano` |
| Přístupová práva k zařízení | `pridej_pristup_zarizeni`, `odeber_pristup_zarizeni`, `dej_pristupy_zarizeni`, `ma_pristup_k_zarizeni`, `muze_editovat_zarizeni` |
| Zprávy/průjezdy | `uloz_zpravu`, `uloz_klasifikaci`, `dej_seznam_zprav`, `dej_zprava_filename`, `dej_zprava_info`, `smaz_zpravu`, `posledni_zprava`, `celkem_paketu`, `dej_pocet_zprav_zarizeni` |
| Přehledy (dashboard) | `dej_prehled_zarizeni`, `dej_prehled_pro_uzivatele` |
| Telemetrie | `uloz_podmínky`, `dej_posledni_podmínky`, `dej_historii_podmínek` |
| Typy vlaků | `dej_seznam_typu_vlaku`, `dej_typ_vlaku`, `pridej_typ_vlaku`, `uprav_typ_vlaku`, `smaz_typ_vlaku`, `dej_train_db_pro_klasifikaci` |

### 13.2 Poznámky k implementaci

- Chybová obsluha je nekonzistentní: některé funkce mají `try/except/finally` s uzavřením spojení i při chybě, jiné (typicky starší, z v1.0) nemají žádné ošetření a při výjimce by nechaly spojení otevřené / propadly by výjimku volajícímu bez kontextu.
- `dej_zarizeni(id)` má `try/except`, který v případě chyby (např. neexistující ID) vrátí slovník s prázdnými řetězci místo `None` nebo výjimky — volající kód se na to musí spoléhat implicitně.
- Parametrizace SQL dotazů (`?` placeholders) je použita důsledně — **SQL injection není u standardních cest zjevně přítomné riziko**.

---

## 14. Webové rozhraní a REST API — přehled endpointů

Legenda sloupce „Auth“: **login** = vyžaduje přihlášení (`Depends(require_login)`), **admin (dep.)** = vyžaduje roli admin přes `Depends(ma_roli("admin"))` (implicitně zahrnuje i přihlášení), **žádná** = bez vynucené kontroly. Stav odpovídá verzi 2.7 — do verze 2.5 včetně byly u řady endpointů kontroly slabší nebo chyběly úplně, viz kap. 18 a Příloha C.

### 14.1 `app.py` (kořenové endpointy)

| Metoda | Cesta | Auth | Popis |
|---|---|---|---|
| GET | `/` | žádná | Redirect na dashboard/login dle session |
| GET | `/add-user` | žádná, self-lock | Vytvoří výchozí admin účet; **od v2.6** funguje jen dokud v DB neexistuje žádný uživatel, poté se natrvalo uzamkne (kap. 18, bod 1) |

### 14.2 `auth_router` — `/auth/*` (`auth/routes.py`)

| Metoda | Cesta | Auth | Popis |
|---|---|---|---|
| GET | `/auth/login` | žádná | Přihlašovací formulář |
| POST | `/auth/login` | žádná, rate-limit | Zpracování přihlášení; **od v2.6** zamyká po 5 chybných pokusech na dané jméno (kap. 9.6) |
| POST | `/auth/check-login` | žádná | AJAX ověření dostupnosti loginu (JSON) |
| GET | `/auth/logout` | žádná | Zrušení session |
| POST | `/auth/change-password` | login | Změna vlastního hesla |
| GET/POST | `/auth/users` | admin (dep.) | Seznam a vytvoření uživatele |
| GET/POST | `/auth/user/{id}` | admin (dep.) | Detail, úprava jména, hesla a rolí uživatele; **od v2.6** vyžaduje roli admin (dřív stačilo pouhé přihlášení, kap. 18 bod 2) |

### 14.3 `device_router` — `/auth/*` (`auth/devices.py`)

| Metoda | Cesta | Auth | Popis |
|---|---|---|---|
| GET | `/auth/dashboard` | login | Hlavní přehled zařízení |
| GET/POST | `/auth/devices` | login | Seznam zařízení (filtrovaný dle ACL) / přidání zařízení |
| GET/POST | `/auth/devices/manage/{id}` | login + `muze_editovat_zarizeni` | Úprava zařízení, správa ACL (`device_access`) |
| GET | `/auth/devices/data/{id}` | login + `ma_pristup_k_zarizeni` | Detail dat zařízení — telemetrie, historie, seznam průjezdů |
| GET | `/auth/api/message/{id}/waveform` | login | JSON — data pro graf (raw/filtrovaná) |
| DELETE | `/auth/api/message/{id}` | login + `muze_editovat_zarizeni` | Smazání záznamu průjezdu (DB + soubor) |
| POST | `/auth/api/message/{id}/classify` | login | Ruční (re)klasifikace |
| GET | `/auth/stats` | login | JSON — souhrnné statistiky; **od v2.6** vyžaduje přihlášení (dřív veřejné, kap. 18 bod 3) |
| GET | `/auth/api/mqtt-log` | login | JSON — posledních 50 MQTT zpráv (in-memory) |
| GET | `/auth/api/dashboard` | login | JSON — data pro auto-refresh dashboardu (15 s) |
| GET/POST | `/auth/train-types` | admin (dep.) | Seznam / přidání typu vlaku; **od v2.7** přes `Depends(ma_roli("admin"))` (dřív ruční `if` v těle funkce, kap. 9.3) |
| GET/POST | `/auth/train-types/edit/{id}` | admin (dep.) | Úprava typu vlaku |
| POST | `/auth/train-types/delete/{id}` | admin (dep.) | Smazání typu vlaku |

### 14.4 `admin_router` — `/auth/admin/*` (`auth/admin.py`)

| Metoda | Cesta | Auth | Popis |
|---|---|---|---|
| GET | `/auth/admin/error-log` | admin (dep.) | Zobrazení chybového logu (posledních 200 záznamů); **od v2.7** přes `Depends(ma_roli("admin"))` (kap. 9.3) |
| POST | `/auth/admin/error-log/clear` | admin (dep.) | Vymazání chybového logu |
| GET | `/auth/admin/mqtt-log` | admin (dep.) | Seznam denních MQTT log souborů |
| GET | `/auth/admin/mqtt-log/{filename}` | admin (dep.) | Detail konkrétního dne (validace jména souboru regexem proti path traversal) |

---

## 15. Frontend — šablony, styly, JavaScript

- **Šablonovací engine:** Jinja2 přes `fastapi.templating.Jinja2Templates` (`helpers.py`), společný kontext `template_context()` doplňuje `current_user`, flash zprávy a `app_version` do každé šablony.
- **Layout:** `layout.html` definuje kostru stránky (topbar, boční menu `nav_bar.html`, hlavní obsah `{% block content %}`), modal pro změnu hesla a globální JS pomocné funkce pro formátování timestampů (`formatTsCell`, `formatTsFmt`) aplikované na všechny prvky s třídou `.ts-cell` / `.ts-fmt` po načtení DOM.
- **CSS:** Bootstrap (lokální statická kopie, žádné CDN) + vlastní `static/style.css` s pojmenovanými třídami (od verze 1.5 zcela nahradily inline `style="…"` atributy v šablonách).
- **Grafy:** Chart.js 4.4.0 + `chartjs-plugin-zoom` + Hammer.js — načítány **z CDN** (`jsdelivr.net`) pouze v `device_data.html` (`{% block js %}`) — jediná externí síťová závislost frontendu; při offline nasazení bez přístupu k internetu graf nebude fungovat.
- **AJAX/polling vzory:**
  - Dashboard: `setInterval(updateDashboard, 15000)` — refresh karet zařízení a statistik bez reloadu stránky.
  - Live MQTT log (jen pro adminy): `setInterval(updateLog, 3000)`.
  - Skrývání karet zařízení na dashboardu je čistě klientská záležitost (`localStorage`, klíč `hidden_devices`) — není perzistentní mezi zařízeními/prohlížeči a neprochází přes server.
- **Grafy signálu:** modální okno (`#chart-overlay`) s canvasem, zoom kolečkem myši, pan tažením, reset zoomu tlačítkem; detekované vrcholy zvýrazněny červenými trojúhelníky (pouze u „zpracovaných“ grafů).

---

## 16. Logování a diagnostika

| Log | Modul | Umístění | Rotace | Obsah |
|---|---|---|---|---|
| Chybový log aplikace | `app_logger.py` | `db/app_error.log` | `RotatingFileHandler`, max 2 MB × 3 zálohy | Neošetřené HTTP výjimky (přes middleware), chyby rozbalení/klasifikace MQTT dat |
| Denní MQTT log | `mqtt_log.py` | `db/mqtt_logs/YYYY-MM-DD.log` | jeden soubor na den, bez limitu velikosti | Textové řádky událostí `COMPLETE`/`INCOMPLETE`/`REJECTED`/`PARSE_ERR`/`CLASSIFY_ERR` |
| Konzolový výstup | `print()` napříč `mqtt_receiver.py`, `data_funkce.py` | stdout kontejneru (`docker compose logs`) | — | Provozní ladicí výpisy, nejde o strukturované logování |

Aplikace nepoužívá standardní `logging` konfiguraci pro obecné INFO zprávy — `print()` je hlavní kanál pro běžný provozní výstup, zatímco modul `logging` (`app_logger`) je vyhrazen výhradně pro chyby úrovně ERROR. Pro produkční observabilitu by bylo vhodné sjednotit na strukturované logování (viz kap. 20).

---

## 17. Nasazení a provoz (Docker)

Podrobný provozní postup je v `SPUSTENI.md`; zde je shrnutí z pohledu vývojáře.

### 17.1 Build

Multi-stage `Dockerfile`:

1. **builder** (`python:3.12-slim`) — instaluje `gcc` (nutné pro sestavení SciPy kola na některých platformách), instaluje závislosti z `requirements.txt` do `/install`.
2. **runtime** (`python:3.12-slim`) — kopíruje jen nainstalované balíčky (`/install → /usr/local`) a zdrojový kód aplikace, vytváří adresáře `db/` a `data_storage/`, spouští `uvicorn app:app --host 0.0.0.0 --port 8000`.

### 17.2 Docker Compose

```yaml
services:
  app:
    build: .
    ports:
      - "127.0.0.1:5000:8000"   # výchozí: přístup jen z lokálního hostitele
    volumes:
      - ./db:/app/db
      - ./data_storage:/app/data_storage
    environment:
      - SECRET_KEY=změňte_mě_na_tajný_řetězec_min_32_znaků
      - TZ=Europe/Prague
    restart: unless-stopped
```

Persistentní data (`db/`, `data_storage/`) jsou bind mounty na hostitelský disk — nezávislé na životním cyklu image, přežijí `docker compose down && up --build`. Port je defaultně publikován **jen na loopback** (`127.0.0.1:5000`) — pro přímý přístup zvenčí je nutné explicitně změnit na `"5000:8000"` (viz `SPUSTENI.md`), typicky ve spojení s reverse proxy (Nginx/Traefik s TLS), která ale **není součástí tohoto repozitáře**.

### 17.3 Prvotní nastavení po nasazení

1. Nastavit `SECRET_KEY` v `docker-compose.yml`.
2. `docker compose up -d --build`.
3. Otevřít `/add-user` v prohlížeči → vytvoří se admin účet `admin` / `admin123`. **Od verze 2.6** se tím endpoint zároveň natrvalo uzamkne (kap. 18, bod 1) — druhé volání už žádný účet nevytvoří.
4. **Doporučeno okamžitě po přihlášení změnit heslo** admin účtu přes „Změnit heslo“ v horní liště aplikace.

---

## 18. Bezpečnost — analýza a známá rizika

Tato kapitola shrnuje bezpečnostně relevantní zjištění z analýzy kódu. Jde o interní hodnocení pro vývojářský tým, nikoli formální penetrační test.

| # | Zjištění | Závažnost | Stav | Popis / doporučení |
|---|---|---|---|---|
| 1 | `GET /add-user` bez autentizace | Vysoká | **Opraveno (v2.6)** | Endpoint se nyní natrvalo uzamkne, jakmile v DB existuje alespoň jeden uživatel (`SELECT COUNT(*) FROM users`) — po vytvoření prvního účtu přestává být zneužitelný. |
| 2 | `GET/POST /auth/user/{id}` bez kontroly role | Vysoká | **Opraveno (v2.6)** | Endpoint nyní vyžaduje `Depends(ma_roli("admin"))` místo pouhého `require_login`. Běžní uživatelé si heslo mění přes samostatný, bezpečný `/auth/change-password`. |
| 3 | `GET /auth/stats` bez autentizace | Nízká | **Opraveno (v2.6)** | Doplněna závislost `Depends(require_login)`. |
| 4 | Hardcoded MQTT přihlašovací údaje | Střední | **Opraveno (v2.6)** | Přesunuto do `DevelopmentConfig.MQTT_HOST/PORT/USERNAME/PASSWORD`, čtených z proměnných prostředí; fallback na původní hodnoty sdíleného kurzovního brokeru zachován, aby se nerozbilo stávající nasazení bez zásahu. |
| 5 | Výchozí slabý `SECRET_KEY` | Střední (mitigováno provozní dokumentací) | Otevřeno | `nastaveni.py` má fallback `'tajny_klic_zmente_v_produkci'`, pokud proměnná prostředí chybí. `SPUSTENI.md` explicitně nabádá k jeho změně, ale kód sám vynucení nekontroluje. |
| 6 | MQTT spojení bez TLS | Nízká–střední | Otevřeno | Vyžaduje ověření, zda sdílený kurzovní broker (`shiftr.io`) vůbec TLS port nabízí — neřešeno naslepo, aby se nerozbilo funkční spojení. |
| 7 | Historie hesel se neuplatňuje | Nízká | Otevřeno | `user_passwords` ukládá historii hashů, ale kontroluje se jen poslední — jde o neškodný mrtvý kód, ne zranitelnost, ponecháno bez zásahu. |
| 8 | Žádný rate-limiting na loginu | Nízká–střední | **Opraveno (v2.6)** | `POST /auth/login` nyní po 5 neúspěšných pokusech na stejné přihlašovací jméno zamkne přihlášení na 60 s. Jde o in-memory limiter (per proces, per `login_name`) — nesdílí se mezi více worker procesy a resetuje se restartem aplikace, viz kap. 9.6. |

---

## 19. Známé nedostatky a technický dluh

- ~~`mqtt/routes.py` je nepoužívaný pozůstatek z dřívější Flask implementace.~~ **Odstraněno ve v2.7.**
- ~~Redundantní DB inicializace: `ensure_device_access_table()`, `ensure_train_types_table()`, `ensure_conditions_table()` v `data_funkce.py` duplikují tabulky, které `init_db()` už vytváří.~~ **Odstraněno ve v2.7** (spolu s nikde nepoužívanou `_require_admin()` v `auth/devices.py`, zjištěnou při stejném úklidu).
- ~~Duplicitní hardcoded databáze typů vlaků na dvou místech.~~ **Sjednoceno ve v2.7** do `nastaveni.TRAIN_TYPES_SEED` (kap. 12.6).
- ~~Nejednotné vynucování administrátorské role (dependency vs. ruční `if`).~~ **Sjednoceno ve v2.7**, viz kap. 9.3.
- **Nekonzistentní styl přístupu k datům:** starší funkce vrací n-tice s přístupem podle indexu (`dev[1]`, `row[0]`), novější `sqlite3.Row` / `dict(r)` s přístupem podle jména sloupce — obojí se používá souběžně i v rámci jedné šablony (`devices.html`). Neřešeno — plošný refaktoring s vysokým rizikem regresí za nejasný přínos, viz kap. 20.
- **Absence automatizovaných testů** — v repozitáři není žádný testovací adresář ani konfigurace (`pytest`, `unittest`). Veškerá verifikace (v2.6 i v2.7) byla dosud jen ruční, byť opakovaně přes `TestClient`.
- **`app = create_app()` na úrovni modulu** — ztěžuje testování (MQTT vlákno a DB inicializace se spustí při pouhém importu), chybí `TESTING`/`CONFIG` přepínač.
- **`mqtt_packets`** tabulka zůstává v schématu, ale nikdy se neplní (funkce, co do ní zapisovala, byla ve v2.7 odstraněna jako mrtvý kód — samotnou tabulku prozatím neodstraňujeme, protože smazání `CREATE TABLE` v `init_db()` by u nových instalací tabulku nevytvořilo, ale u existujících databází by neškodně zůstala; jde jen o kosmetický dluh).

### 19.1 Poznámka k rozsahu úklidu ve v2.7

Úklid v této verzi se záměrně omezil na **bezpečně smazatelný mrtvý kód** (nic, co se odkudkoli volá) a **jednu mechanickou konsolidaci dat** (databáze typů vlaků). Sjednocení vynucování admin role šlo o krok dál — dotklo se 10 endpointů a dvou sdílených komponent (dependency, exception handler) — ale bylo provedeno s vědomím vedlejších dopadů (změna cíle přesměrování, přidání flash zpráv) a ověřeno smoke testem s reálným admin i non-admin uživatelem. Zbylé body v této kapitole jsou vědomě ponechány beze změny — buď je jejich přínos nejasný vůči riziku (styl přístupu k datům), nebo jde o samostatné, větší architektonické rozhodnutí (testovatelnost `app.py`), ne o „úklid“.

---

## 20. Doporučení pro další vývoj

1. ~~Bezpečnost především: odstranit/zabezpečit `/add-user`, doplnit kontrolu role u `/auth/user/{id}`, zvážit autentizaci i pro `/auth/stats`.~~ **Provedeno ve v2.6** (viz kap. 18, body 1–3).
2. ~~Sjednotit vynucování autorizace výhradně na `Depends(ma_roli(...))`.~~ **Provedeno ve v2.7** (viz kap. 9.3) — všech 10 dříve ručně kontrolovaných endpointů nyní používá dependency injection.
3. ~~Přesunout MQTT broker credentials do proměnných prostředí (analogicky k `SECRET_KEY`).~~ **Provedeno ve v2.6** (viz kap. 18, bod 4).
4. Zavést alespoň základní testovací sadu (`pytest` + `TestClient` z FastAPI) — oddělit vytváření `app` instance od testovací konfigurace DB (např. dočasný SQLite soubor / in-memory DB). Opakované manuální smoke testy přes `TestClient` při opravách v2.6 a v2.7 ukazují, že je to proveditelné bez větších zásahů — zbývá je jen zafixovat jako trvalou testovací sadu místo jednorázových skriptů.
5. Zvážit oddělení `classifier.py` konstant (práh peak detekce, PSD práh, frekvenční pásma) do konfigurace, aby šly ladit bez zásahu do kódu — případně je zpřístupnit administrátorovi v UI podobně jako `train_types`.
6. ~~Odklidit mrtvý kód (`mqtt/routes.py`, redundantní `ensure_*_table` funkce).~~ **Provedeno ve v2.7.**
7. Zvážit strukturované logování (JSON logy) místo `print()` pro snazší napojení na externí monitoring.
8. Doplnit periodický (časovačem řízený) úklid `packet_buffers`, nezávislý na příchodu další MQTT zprávy.
9. Rate-limiting z v2.6 (kap. 9.6) je jen per-proces — při budoucím škálování na více workerů přesunout stav do sdíleného úložiště (Redis apod.).
10. Zvážit detekci a nahlas logované varování při startu, pokud je stále aktivní výchozí `SECRET_KEY` (kap. 18, bod 5) — zatím neimplementováno.

---

## Příloha A — SQL schéma databáze (zjednodušené DDL)

```sql
CREATE TABLE users (
    user_id  INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    name     TEXT NOT NULL,
    surname  TEXT,
    login    TEXT UNIQUE,
    created  TEXT DEFAULT (CURRENT_TIMESTAMP)
);

CREATE TABLE user_passwords (
    pass_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER REFERENCES users(user_id) NOT NULL,
    password NOT NULL,
    created  TEXT DEFAULT (CURRENT_TIMESTAMP)
);

CREATE TABLE system_roles (
    role_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name        NOT NULL,
    description TEXT,
    sysid       TEXT UNIQUE NOT NULL
);

CREATE TABLE user_roles (
    user_role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER REFERENCES users(user_id),
    role_id      INTEGER REFERENCES system_roles(role_id),
    assigned     TEXT DEFAULT (CURRENT_TIMESTAMP),
    removed      TEXT,
    responsible  INTEGER REFERENCES users(user_id)
);

CREATE TABLE devices (
    device_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id  TEXT UNIQUE NOT NULL,
    assigned   TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    user_id    INTEGER REFERENCES users(user_id),
    location   TEXT,
    description TEXT
);

CREATE TABLE messages (
    message_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       INTEGER REFERENCES devices(device_id) NOT NULL,
    assigned        TEXT DEFAULT (CURRENT_TIMESTAMP),
    measured_at     TEXT,
    topic           TEXT,
    packets         INTEGER,
    filename        TEXT UNIQUE,
    train_type      TEXT,
    speed_kmh       REAL,
    damage_detected INTEGER,
    classified_at   TEXT,
    is_complete     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE mqtt_packets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id     TEXT,
    topic         TEXT,
    timestamp     TEXT,
    packet_nr     INTEGER,
    total_packets INTEGER,
    created_at    TEXT DEFAULT (CURRENT_TIMESTAMP)
);

CREATE TABLE device_conditions (
    condition_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       INTEGER NOT NULL REFERENCES devices(device_id),
    received_at     TEXT NOT NULL,
    temperature     REAL,
    humidity        REAL,
    pressure        REAL,
    batt_mv         INTEGER,
    signal_strength INTEGER,
    uptime_minutes  INTEGER,
    train_counter   INTEGER
);

CREATE TABLE device_access (
    access_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES devices(device_id),
    user_id   INTEGER NOT NULL REFERENCES users(user_id),
    can_edit  INTEGER NOT NULL DEFAULT 0,
    assigned  TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(device_id, user_id)
);

CREATE TABLE train_types (
    train_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
    typ           TEXT NOT NULL UNIQUE,
    pomer         REAL NOT NULL,
    dvojkoli_mm   INTEGER NOT NULL,
    popis         TEXT DEFAULT '',
    created       TEXT DEFAULT (datetime('now','localtime'))
);
```

---

## Příloha B — Formát binárních paketů (bajt po bajtu)

### B.1 Datový paket — 8 212 B celkem

| Offset (B) | Délka | Typ | Pole |
|---|---|---|---|
| 0 | 2 | uint16 | packet_header |
| 2 | 2 | uint16 | packet_version |
| 4 | 2 | uint16 | actual_packet_nr |
| 6 | 2 | uint16 | total_packet_nr |
| 8 | 4 | uint32 | timestamp |
| 12 | 4 | uint32 | total_sample_count |
| 16 | 2 | uint16 | train_counter |
| 18 | 2048 | int16×1024 | chan_0_vlt |
| 2066 | 2048 | int16×1024 | chan_0_int |
| 4114 | 2048 | int16×1024 | chan_1_vlt |
| 6162 | 2048 | int16×1024 | chan_1_int |
| 8210 | 2 | uint16 | CRC |

### B.2 Telemetrický paket V1 — 72 B celkem

| Offset (B) | Délka | Typ | Pole |
|---|---|---|---|
| 0 | 2 | uint16 | packet_header |
| 2 | 1 | uint8 | packet_ver_major |
| 3 | 1 | uint8 | packet_ver_minor |
| 4 | 4 | uint32 | timestamp |
| 8 | 2 | uint16 | reserve_word |
| 10 | 2 | uint16 | packet_counter |
| 12 | 2 | uint16 | batt_voltage (mV) |
| 14 | 4 | int32 | unit_temperature (°C × 1000) |
| 18 | 4 | uint32 | unit_humidity (% × 1000) |
| 22 | 4 | uint32 | unit_pressure (Pa × 1000) |
| 26 | 4 | uint32 | IMEI |
| 30 | 4 | uint32 | DEV_ID |
| 34 | 2 | uint16 | train_counter |
| 36 | 2 | uint16 | pwr_cycle_counter |
| 38 | 4 | uint32 | uptime_minutes |
| 42 | 4 | uint32 | last_powercycle_timestamp |
| 46 | 2 | uint16 | unit_status_bits |
| 48 | 2 | int16 | signal_strength (dBm) |
| 50 | 2 | int16 | signal_rsrp |
| 52 | 2 | int16 | signal_rsrq |
| 54 | 2 | int16 | signal_snr |
| 56 | 2 | uint16 | modem_status_word |
| 58 | 4 | float | GPS_lat |
| 62 | 4 | float | GPS_lon |
| 66 | 4 | float | GPS_alt |
| 70 | 2 | uint16 | CRC |

### B.3 Telemetrický paket V2 — 76 B celkem

Shodný s V1, ale ihned za `packet_ver_minor` (offset 4) jsou vloženy 4 nové bajty: `hw_ver_major` (uint8), `hw_ver_minor` (uint8), `sw_ver_major` (uint8), `sw_ver_minor` (uint8) — všechna následující pole jsou tím posunuta o 4 B oproti V1.

---

## Příloha C — Historie verzí (výtah z `CHANGELOG.md`)

| Verze | Datum | Shrnutí |
|---|---|---|
| 2.7 | 2026-07-17 | Úklid technického dluhu: smazán mrtvý kód (Flask pozůstatek, redundantní DB inicializace, `_require_admin`), sjednocena databáze typů vlaků a vynucování admin role |
| 2.6 | 2026-07-17 | Zabezpečení: uzamčení `/add-user`, admin-only `/auth/user/{id}`, autentizace `/auth/stats`, MQTT credentials do env proměnných, rate-limiting loginu |
| 2.5 | 2026-07-17 | Oprava `dej_zarizeni()`: chybný SQL parametr u dvouciferných `device_id`, chybějící `conn.close()` |
| 2.4 | 2026-06-25 | Oprava timeoutu bufferu (měří mezeru mezi pakety); `BUFFER_TIMEOUT_SECONDS` přesunuto do `nastaveni.py` |
| 2.3 | 2026-06-24 | Indikátor „UNIT ALIVE“ na dashboardu |
| 2.2 | 2026-06-24 | Sjednocení stylu tlačítka v detailu MQTT logu |
| 2.1 | 2026-06-24 | Denní MQTT log + admin stránky pro jeho prohlížení |
| 2.0 | 2026-06-24 | Přepracování klíče packet bufferu na `(device_id, device_ts)` |
| 1.9 | 2026-06-19 | Ukládání neúplných zpráv po timeoutu (`is_complete`) |
| 1.8 | 2026-06-17 | Oprava zobrazení času (lokální čas místo UTC) |
| 1.7 | 2026-06-17 | Chybový log aplikace, podpora SYS V1/V2, oddělené grafy raw/zpracovaná data |
| 1.6 | 2026-06-17 | Mazání záznamu průjezdu |
| 1.5 | 2026-06-17 | Docker Compose s named volumes, CSS refaktoring |
| 1.4 | 2026-06-16 | Auto-refresh dashboardu, automatická klasifikace po přijetí, sloupec `measured_at` |
| 1.3 | 2026-05-29 | Dashboard, napojení na MQTT broker, binární příjem dat |
| 1.2–1.0 | 2025-07 až 2025-08 | Základ FastAPI aplikace, autentizace, správa zařízení, klasifikátor, grafy |

Kompletní a průběžně aktualizovaná historie je vedena v souboru `CHANGELOG.md` v kořeni repozitáře.

---

*Konec dokumentu.*
