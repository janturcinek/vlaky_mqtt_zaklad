# Průjezdy vlaků — spuštění na serveru

## Co potřebuješ mít nainstalované
- Docker (≥ 24) + Docker Compose plugin
- Ověření: `docker compose version`

---

## 1. Příprava

Rozbal ZIP do libovolné složky, např. `/opt/vlaky`.

**Povinné: nastav tajný klíč** — otevři `docker-compose.yml` a změň řádek:

```yaml
- SECRET_KEY=změňte_mě_na_tajný_řetězec_min_32_znaků
```

na např.:

```yaml
- SECRET_KEY=muj_super_tajny_klic_1234567890ab
```

**Volitelné: změna portu** — ve výchozím nastavení je aplikace dostupná pouze z té samé mašiny
(localhost:5000). Pro přímý přístup z venku bez reverse proxy změň:

```yaml
ports:
  - "5000:8000"
```

---

## 2. První spuštění

```bash
cd /opt/vlaky
docker compose up -d --build
```

Data jsou ukládána do složek `./db/` a `./data_storage/` přímo ve složce projektu
(bind mounty). Tyto složky **nejsou součástí gitu** a **rebuild je nijak neovlivní** —
přepsání souborů aplikace je neovlivní, dokud nepřepíšeš samotné složky.

---

## 3. Vytvoření prvního admin účtu

Po spuštění otevři v prohlížeči:

```
http://<adresa-serveru>:5000/add-user
```

Vytvoř admin uživatele (zapamatuj si přihlašovací údaje).

---

## 4. Přihlášení a používání

```
http://<adresa-serveru>:5000/
```

---

## 5. Správa kontejneru

```bash
# Stav
docker compose ps

# Logy (živě)
docker compose logs -f

# Zastavit / spustit
docker compose stop
docker compose start

# Smazat kontejner (data ve složkách zůstanou!)
docker compose down

# Rebuild a spuštění (data ve složkách zůstanou!)
docker compose down && docker compose up -d --build
```

---

## 6. Aktualizace aplikace (nová verze ZIPu)

```bash
docker compose down
# přepiš soubory novou verzí ZIPu
# POZOR: zachovej složky db/ a data_storage/ — obsahují data!
# POZOR: zachovej docker-compose.yml se svým SECRET_KEY
docker compose up -d --build
```

Složky `./db/` a `./data_storage/` jsou na hostitelském disku — přepsání souborů aplikace je neovlivní.

---

## 7. Zálohování dat

```bash
# Záloha databáze
tar czf db_backup_$(date +%Y%m%d).tar.gz db/

# Záloha binárních souborů průjezdů
tar czf data_backup_$(date +%Y%m%d).tar.gz data_storage/
```

---

## 8. Obnova dat ze zálohy

```bash
tar xzf db_backup_YYYYMMDD.tar.gz
tar xzf data_backup_YYYYMMDD.tar.gz
```

---

## Datové složky

| Složka           | Obsah                           | V gitu |
|------------------|---------------------------------|--------|
| `./db/`          | SQLite databáze (`vlaky.db`)    | Ne     |
| `./data_storage/`| Binární soubory průjezdů (.bin) | Ne     |

---

## Síťové požadavky

| Port | Směr    | Popis                                      |
|------|---------|--------------------------------------------|
| 5000 | příchozí| HTTP aplikace                              |
| 1883 | odchozí | MQTT broker `iot-course-but.cloud.shiftr.io` |
