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

Docker automaticky vytvoří dva pojmenované volumes (`vlaky_db` a `vlaky_data`)
pro databázi a binární soubory průjezdů. Tyto volumes jsou spravovány Dockerem
a **nejsou závislé na složce s aplikací** — přepsání souborů aplikace je neovlivní.

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

# Smazat kontejner (volumes zůstanou!)
docker compose down

# Smazat kontejner I volumes (SMAŽE DATA!)
docker compose down -v
```

---

## 6. Aktualizace aplikace (nová verze ZIPu)

```bash
docker compose down
# přepiš soubory novou verzí ZIPu (zachovej docker-compose.yml se svým SECRET_KEY)
docker compose up -d --build
```

Volumes `vlaky_db` a `vlaky_data` přetrvají — data jsou v bezpečí.

---

## 7. Zálohování dat

```bash
# Záloha databáze
docker run --rm \
  -v vlaky_db:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/db_backup_$(date +%Y%m%d).tar.gz -C /data .

# Záloha binárních souborů průjezdů
docker run --rm \
  -v vlaky_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/data_backup_$(date +%Y%m%d).tar.gz -C /data .
```

---

## 8. Obnova dat ze zálohy

```bash
# Obnova databáze
docker run --rm \
  -v vlaky_db:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/db_backup_YYYYMMDD.tar.gz -C /data

# Obnova binárních souborů
docker run --rm \
  -v vlaky_data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/data_backup_YYYYMMDD.tar.gz -C /data
```

---

## 9. Přenos existujících dat (migrace z bind mountů)

Pokud jsi dříve používal bind mounty (`./db/`, `./data_storage/`) a chceš data
přenést do nových volumes:

```bash
# Spusť jednou (vytvoří volumes)
docker compose up -d --build

# Zkopíruj databázi do volume
docker run --rm \
  -v $(pwd)/db:/src \
  -v vlaky_db:/dst \
  alpine cp -r /src/. /dst/

# Zkopíruj binární soubory
docker run --rm \
  -v $(pwd)/data_storage:/src \
  -v vlaky_data:/dst \
  alpine cp -r /src/. /dst/
```

---

## Přehled volumes

| Volume       | Obsah                          | Smazat lze pouze s `-v` |
|--------------|--------------------------------|------------------------|
| `vlaky_db`   | SQLite databáze (`vlaky.db`)   | Ano                    |
| `vlaky_data` | Binární soubory průjezdů (.bin)| Ano                    |

## Síťové požadavky

| Port | Směr    | Popis                                      |
|------|---------|--------------------------------------------|
| 5000 | příchozí| HTTP aplikace                              |
| 1883 | odchozí | MQTT broker `iot-course-but.cloud.shiftr.io` |
