import os
import sqlite3
from werkzeug.security import generate_password_hash,check_password_hash
from nastaveni import WAVE_SAMPLE_LEN, DevelopmentConfig
from datetime import datetime

def get_db_connection():
    """Vytvoří připojení k databázi"""
    os.makedirs(os.path.dirname(DevelopmentConfig.DATABASE), exist_ok=True)
    conn = sqlite3.connect(DevelopmentConfig.DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Inicializuje databázi při startu aplikace.
    Vytvoří všechny tabulky (pokud neexistují) a seeduje základní data.
    Bezpečné volat opakovaně – neničí existující data.
    """
    conn = get_db_connection()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id  INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            name     TEXT NOT NULL,
            surname  TEXT,
            login    TEXT UNIQUE,
            created  TEXT DEFAULT (CURRENT_TIMESTAMP)
        );

        CREATE TABLE IF NOT EXISTS user_passwords (
            pass_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  INTEGER REFERENCES users(user_id) NOT NULL,
            password NOT NULL,
            created  TEXT DEFAULT (CURRENT_TIMESTAMP)
        );

        CREATE TABLE IF NOT EXISTS system_roles (
            role_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            name        NOT NULL,
            description TEXT,
            sysid       TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_roles (
            user_role_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER REFERENCES users(user_id),
            role_id      INTEGER REFERENCES system_roles(role_id),
            assigned     TEXT DEFAULT (CURRENT_TIMESTAMP),
            removed      TEXT,
            responsible  INTEGER REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS devices (
            device_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id  TEXT UNIQUE NOT NULL,
            assigned   TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
            user_id    INTEGER REFERENCES users(user_id),
            location   TEXT,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS messages (
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
            classified_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS mqtt_packets (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id     TEXT,
            topic         TEXT,
            timestamp     TEXT,
            packet_nr     INTEGER,
            total_packets INTEGER,
            created_at    TEXT DEFAULT (CURRENT_TIMESTAMP)
        );

        CREATE TABLE IF NOT EXISTS device_conditions (
            condition_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id       INTEGER NOT NULL,
            received_at     TEXT NOT NULL,
            temperature     REAL,
            humidity        REAL,
            pressure        REAL,
            batt_mv         INTEGER,
            signal_strength INTEGER,
            uptime_minutes  INTEGER,
            train_counter   INTEGER,
            FOREIGN KEY (device_id) REFERENCES devices(device_id)
        );

        CREATE TABLE IF NOT EXISTS device_access (
            access_id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER NOT NULL,
            user_id   INTEGER NOT NULL,
            can_edit  INTEGER NOT NULL DEFAULT 0,
            assigned  TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(device_id, user_id),
            FOREIGN KEY (device_id) REFERENCES devices(device_id),
            FOREIGN KEY (user_id)   REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS train_types (
            train_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            typ           TEXT NOT NULL UNIQUE,
            pomer         REAL NOT NULL,
            dvojkoli_mm   INTEGER NOT NULL,
            popis         TEXT DEFAULT '',
            created       TEXT DEFAULT (datetime('now','localtime'))
        );
    """)

    # Seed: systémové role
    c.execute("INSERT OR IGNORE INTO system_roles (name, sysid) VALUES ('Admin', 'admin')")
    c.execute("INSERT OR IGNORE INTO system_roles (name, sysid) VALUES ('User',  'user')")

    # Seed: typy vlaků
    for t in _TRAIN_DB_SEED:
        c.execute(
            "INSERT OR IGNORE INTO train_types (typ, pomer, dvojkoli_mm, popis) VALUES (?, ?, ?, ?)",
            (t["typ"], t["pomer"], t["dvojkoli_mm"], t["popis"])
        )

    # Migrace: přidej measured_at do existujících DB
    c.execute("PRAGMA table_info(messages)")
    existing_cols = {row[1] for row in c.fetchall()}
    if "measured_at" not in existing_cols:
        c.execute("ALTER TABLE messages ADD COLUMN measured_at TEXT")

    conn.commit()
    conn.close()
    print("[DB] init_db() dokončen")


def is_user(login):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT user_id, name, surname FROM users WHERE login = ?", (login,))
    user_row = c.fetchone()
    conn.close()
    return user_row
        

def pass_ok(user_id,heslo):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT password FROM user_passwords WHERE user_id = ? ORDER BY created DESC LIMIT 1", (user_id,))
    pass_row = c.fetchone()
    conn.close()
    return check_password_hash(pass_row[0], heslo)

def uloz_uzivatele(form):
    jmeno=form["jmeno"]
    prijmeni=form["prijmeni"]
    login=form["login"]
    heslo= generate_password_hash(form["heslo"])
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO users (name, surname, login) VALUES (?, ?, ?)",(jmeno, prijmeni, login))
    user_id = c.lastrowid
    # Vlož heslo (hash)
    c.execute("INSERT INTO user_passwords (user_id, password) VALUES (?, ?)",
                (user_id, heslo))

    conn.commit()
    conn.close()

def zmen_uzivatele(user_id,form):
    jmeno=form["jmeno"]
    prijmeni=form["prijmeni"]
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("Update users set name=?, surname=? where user_id=?",(jmeno, prijmeni, user_id))
    conn.commit()
    conn.close()

def zmen_heslo(user_id,form):
    heslo= generate_password_hash(form["heslo"])
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO user_passwords (user_id, password) VALUES (?, ?)",
                (user_id, heslo))
    conn.commit()
    conn.close()
        
def login_check(login):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE login = ?", (login,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def seznam_uzivatelu():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT user_id,name,surname,login FROM users order by user_id desc")
    uziv=c.fetchall()
    conn.close()
    return uziv


def seznam_roli():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT role_id,name FROM system_roles order by role_id")
    roles=c.fetchall()
    conn.close()
    return roles

def pocet_adminu():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            SELECT COUNT(*) 
            FROM user_roles 
            WHERE role_id = 1 AND removed IS NULL
        """)
        
        result = c.fetchone()
        return result[0] if result else 0
    except Exception as e:
        print(f"Chyba při počítání administrátorů: {e}")
        return 0
    finally:
        if conn:
            conn.close()

def pridej_roli(user, role):
    conn = get_db_connection()
    c = conn.cursor()
    # Zkontroluj, jestli uživatel už má tuto roli aktivní
    c.execute("SELECT 1 FROM user_roles WHERE user_id = ? AND role_id = ? AND removed IS NULL", (user, role) )
    exists = c.fetchone()
    if exists:
        conn.close()
        return False  # Roli už má, nevkládáme znovu
    # Roli nemá, vlož ji
    c.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (user, role))
    conn.commit()
    conn.close()
    return True

def odeber_roli(user_role_id):
    from datetime import datetime
    try:
        conn = get_db_connection()
        c = conn.cursor()
        # Nastav removed na aktuální čas
        removed_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        c.execute(
            "UPDATE user_roles SET removed = ? WHERE user_role_id = ? AND removed IS NULL",
            (removed_time, user_role_id)
        )
        
        conn.commit()
        return c.rowcount > 0  # Vrátí True pokud byl záznam aktualizován
    except Exception as e:
        # Pro debugging nebo logování
        print(f"Chyba při odebírání role: {e}")
        return False
    finally:
        if conn:
            conn.close()

def dej_user_role_detail(user_role_id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""
            SELECT user_id, role_id, assigned, removed
            FROM user_roles
            WHERE user_role_id = ?
        """, (user_role_id,))
        data = c.fetchone()
        
        if data:
            return { "user_id": data[0],"role_id": data[1],"assigned": data[2],"removed": data[3] }
        else:
            return None
    except Exception as e:
        print(f"Chyba při načítání detailu role: {e}")
        return None
    finally:
        if conn:
            conn.close()
def ma_roli(user_id,sysid):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""
            SELECT 1
            FROM user_roles ur
            JOIN system_roles r ON ur.role_id = r.role_id
            WHERE ur.user_id = ? AND r.sysid=? and ur.removed IS NULL
        """, (user_id,sysid))
        ano = c.fetchone()
        conn.close()
        if not ano:
            return False
        else:
            return True
    except Exception as e:
        print(e)
        return False

def dej_detail_uzivatele(id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Načtení základních údajů o uživateli
        c.execute("SELECT name, surname, login FROM users WHERE user_id = ?", (id,))
        data = c.fetchone()
        if not data:
            return None
        
        # Načtení přiřazených aktivních rolí
        c.execute("""
            SELECT ur.user_role_id, r.name, assigned
            FROM user_roles ur
            JOIN system_roles r ON ur.role_id = r.role_id
            WHERE ur.user_id = ? AND ur.removed IS NULL
        """, (id,))
        
        role_data = c.fetchall()
        roles = []
        for row in role_data:
            roles.append({"user_role_id": row[0],"role_name": row[1],"assigned": row[2]})
        
        # Výsledek jako slovník
        return {"name": data[0],"surname": data[1],"login": data[2],"roles": roles}
    
    except Exception as e:
        print(e)
        # Můžeš zalogovat chybu např. print(e) nebo logger.error(e)
        return None
    
    finally:
        if conn:
            conn.close()
    

def save_packet_to_db(device_id, topic, timestamp, packet_nr, total_packets):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO mqtt_packets (client_id, topic, timestamp, packet_nr, total_packets)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            device_id,
            topic,
            timestamp,
            packet_nr,
            total_packets
        ))
        conn.commit()
    except Exception as e:
        print("nepodařilo se uložit z následujícího důvodu: ",e)
    conn.close()
    
def celkem_paketu():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT sum(packets) FROM messages")
    out=c.fetchone()[0]
    conn.close()
    return out    
    
def dej_seznam_zarizeni():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""SELECT device_id,client_id, location,assigned, name,surname 
                FROM devices join users using(user_id) order by assigned desc""")
    devices=c.fetchall()
    conn.close()
    return devices


def dej_seznam_zarizeni_pro_uzivatele(user_id: int, is_admin: bool):
    """Vrátí seznam zařízení filtrovaný dle přístupových práv."""
    conn = get_db_connection()
    c = conn.cursor()
    if is_admin:
        c.execute("""SELECT device_id, client_id, location, assigned, name, surname
                     FROM devices JOIN users USING(user_id)
                     ORDER BY assigned DESC""")
    else:
        c.execute("""SELECT device_id, client_id, location, assigned, name, surname
                     FROM devices JOIN users USING(user_id)
                     WHERE device_id IN (
                         SELECT device_id FROM devices WHERE user_id = ?
                         UNION
                         SELECT device_id FROM device_access WHERE user_id = ?
                     )
                     ORDER BY assigned DESC""", (user_id, user_id))
    devices = c.fetchall()
    conn.close()
    return devices

def dej_zarizeni(id):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""SELECT device_id,client_id, location,assigned, name,surname,description 
                    FROM devices join users using(user_id) where device_id=?""",(id))
        device=c.fetchone()
        conn.close
        device={"device_id":device[0],"oznaceni":device[1],"poloha":device[2],"vlozil": f"{device[4]} {device[5]}","vlozeno":device[3],"popis":device[6]}
    except Exception as e:
        print(e)
        device={"device_id":"","oznaceni":"","poloha":"","vlozil": "","vlozeno":"","popis":""}    
    return device

def pridej_zarizeni(user_id,form):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO devices (client_id, user_id, location, description)
        VALUES (?, ?, ?, ?)
    ''', (
        form["oznaceni"],
        user_id,
        form["poloha"],
        form["popis"]
    ))
    conn.commit()
    conn.close()
def uprav_zarizeni(device_id,form):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        UPDATE devices set client_id=?, location=?, description=?
        where device_id=?
    ''', (
        form["oznaceni"],
        form["poloha"],
        form["popis"],
        device_id
    ))
    conn.commit()
    conn.close()
    
def dej_pocet_zarizeni():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(DISTINCT client_id) FROM mqtt_packets")
    out=c.fetchone()[0]
    conn.close()
    return out



def registerovano(client_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT device_id FROM devices WHERE client_id = ?", (client_id,))
    result = c.fetchone()
    conn.close()
    if result is not None:
        return result[0]
    else:
        None
        
def posledni_zprava():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
              SELECT client_id, packets, messages.assigned from 
              messages join devices using(device_id) where
              message_id = (SELECT max(message_id) FROM messages)""")
    result = c.fetchone()
    conn.close()
    return result

def uloz_zpravu(device_id, topic, total_packets, filename, measured_at=None):
    conn = get_db_connection()
    c = conn.cursor()
    message_id = None
    try:
        c.execute(
            "INSERT INTO messages (device_id, topic, packets, filename, measured_at) VALUES (?, ?, ?, ?, ?)",
            (device_id, topic, total_packets, filename, measured_at)
        )
        conn.commit()
        message_id = c.lastrowid
    except Exception as e:
         print("nepodařilo se uložit z následujícího důvodu: ",e)
    conn.close()
    return message_id


def uloz_klasifikaci(message_id: int, result: dict):
    """Uloží výsledek automatické klasifikace vlaku do záznamu zprávy."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE messages
            SET train_type = ?, speed_kmh = ?, damage_detected = ?,
                classified_at = datetime('now','localtime')
            WHERE message_id = ?
        """, (
            result.get("typ_vlaku"),
            result.get("rychlost_kmh"),
            1 if result.get("poskozeni_podvozku") else 0,
            int(message_id)
        ))
        conn.commit()
    except Exception as e:
        print(f"Chyba při ukládání klasifikace: {e}")
    conn.close()
    
def dej_pocet_zprav_zarizeni(device_id: int) -> int:
    """Vrátí počet přijatých zpráv (vlaků) pro dané zařízení."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM messages WHERE device_id = ?", (int(device_id),))
    count = c.fetchone()[0]
    conn.close()
    return count


def dej_prehled_zarizeni():
    """Vrátí seznam všech zařízení s aktuálními podmínkami a statistikami vlaků."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT
            d.device_id,
            d.client_id,
            d.location,
            d.description,
            (SELECT COUNT(*) FROM messages m WHERE m.device_id = d.device_id) AS total_trains,
            (SELECT COUNT(*) FROM messages m WHERE m.device_id = d.device_id
               AND COALESCE(m.measured_at, m.assigned) >= datetime('now', '-7 days')) AS trains_week,
            (SELECT m.assigned FROM messages m WHERE m.device_id = d.device_id
               ORDER BY m.message_id DESC LIMIT 1) AS last_train_time,
            (SELECT dc.temperature FROM device_conditions dc WHERE dc.device_id = d.device_id
               ORDER BY dc.condition_id DESC LIMIT 1) AS temperature,
            (SELECT dc.humidity FROM device_conditions dc WHERE dc.device_id = d.device_id
               ORDER BY dc.condition_id DESC LIMIT 1) AS humidity,
            (SELECT dc.batt_mv FROM device_conditions dc WHERE dc.device_id = d.device_id
               ORDER BY dc.condition_id DESC LIMIT 1) AS batt_mv,
            (SELECT dc.signal_strength FROM device_conditions dc WHERE dc.device_id = d.device_id
               ORDER BY dc.condition_id DESC LIMIT 1) AS signal_strength,
            (SELECT dc.received_at FROM device_conditions dc WHERE dc.device_id = d.device_id
               ORDER BY dc.condition_id DESC LIMIT 1) AS conditions_at
        FROM devices d
        ORDER BY d.assigned DESC
    """)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Správa přístupů k zařízením ─────────────────────────────────────────────

def ensure_device_access_table():
    """Vytvoří tabulku device_access, pokud neexistuje."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS device_access (
            access_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id  INTEGER NOT NULL,
            user_id    INTEGER NOT NULL,
            can_edit   INTEGER NOT NULL DEFAULT 0,
            assigned   TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(device_id, user_id),
            FOREIGN KEY (device_id) REFERENCES devices(device_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    conn.commit()
    conn.close()


# ── Databáze typů lokomotiv / vlaků ─────────────────────────────────────────

_TRAIN_DB_SEED = [
    {"typ": "CZLoko1",            "pomer": 1.791667, "dvojkoli_mm": 2400, "popis": ""},
    {"typ": "CZLoko2",            "pomer": 2.75,     "dvojkoli_mm": 2400, "popis": ""},
    {"typ": "Škoda 380",          "pomer": 2.48,     "dvojkoli_mm": 2500, "popis": ""},
    {"typ": "ALSTOM TRAXX 160",   "pomer": 2.988462, "dvojkoli_mm": 2600, "popis": ""},
    {"typ": "ALSTOM TRAXX 160B",  "pomer": 2.996154, "dvojkoli_mm": 2600, "popis": ""},
    {"typ": "ALSTOM TRAXX 140",   "pomer": 3.015385, "dvojkoli_mm": 2600, "popis": ""},
    {"typ": "SIEMENS Vectron Dual","pomer": 3.0,     "dvojkoli_mm": 2700, "popis": ""},
    {"typ": "SIEMENS Vectron CD", "pomer": 2.166667, "dvojkoli_mm": 3000, "popis": ""},
    {"typ": "SIEMENS Vectron",    "pomer": 2.3,      "dvojkoli_mm": 3000, "popis": ""},
    {"typ": "Škoda 363",          "pomer": 1.59375,  "dvojkoli_mm": 3200, "popis": ""},
    {"typ": "Pendolino",          "pomer": 6.037037, "dvojkoli_mm": 2700, "popis": "Jednotka ETR 470"},
    {"typ": "LEO Express",        "pomer": 4.925926, "dvojkoli_mm": 2700, "popis": ""},
    {"typ": "Panter",             "pomer": 6.916667, "dvojkoli_mm": 2400, "popis": ""},
    {"typ": "Elefant",            "pomer": 6.3,      "dvojkoli_mm": 2600, "popis": ""},
    {"typ": "Newag Dragon 2",     "pomer": 1.00,     "dvojkoli_mm": 1950, "popis": ""},
]


def ensure_train_types_table():
    """Vytvoří tabulku train_types a naplní ji výchozími hodnotami."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS train_types (
            train_type_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            typ            TEXT NOT NULL UNIQUE,
            pomer          REAL NOT NULL,
            dvojkoli_mm    INTEGER NOT NULL,
            popis          TEXT DEFAULT '',
            created        TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.commit()
    # Osívování výchozími hodnotami (přeskočí existující)
    for t in _TRAIN_DB_SEED:
        c.execute("""
            INSERT OR IGNORE INTO train_types (typ, pomer, dvojkoli_mm, popis)
            VALUES (?, ?, ?, ?)
        """, (t["typ"], t["pomer"], t["dvojkoli_mm"], t["popis"]))
    conn.commit()
    conn.close()


def dej_seznam_typu_vlaku():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT train_type_id, typ, pomer, dvojkoli_mm, popis, created FROM train_types ORDER BY typ")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def dej_typ_vlaku(train_type_id: int):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT train_type_id, typ, pomer, dvojkoli_mm, popis FROM train_types WHERE train_type_id = ?",
              (int(train_type_id),))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def pridej_typ_vlaku(typ: str, pomer: float, dvojkoli_mm: int, popis: str = ""):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO train_types (typ, pomer, dvojkoli_mm, popis) VALUES (?, ?, ?, ?)",
              (typ.strip(), float(pomer), int(dvojkoli_mm), popis.strip()))
    conn.commit()
    conn.close()


def uprav_typ_vlaku(train_type_id: int, typ: str, pomer: float, dvojkoli_mm: int, popis: str = ""):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE train_types SET typ=?, pomer=?, dvojkoli_mm=?, popis=?
        WHERE train_type_id=?
    """, (typ.strip(), float(pomer), int(dvojkoli_mm), popis.strip(), int(train_type_id)))
    conn.commit()
    conn.close()


def smaz_typ_vlaku(train_type_id: int):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM train_types WHERE train_type_id = ?", (int(train_type_id),))
    conn.commit()
    conn.close()


def dej_train_db_pro_klasifikaci():
    """Vrátí seznam diktů ve formátu kompatibilním s TRAIN_DB pro classifier.py."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT typ, pomer, dvojkoli_mm FROM train_types ORDER BY typ")
    rows = c.fetchall()
    conn.close()
    return [{"typ": r[0], "pomer": r[1], "dvojkoli_mm": r[2]} for r in rows]


def pridej_pristup_zarizeni(device_id: int, user_id: int, can_edit: int = 0):
    """Přidá nebo aktualizuje přístup uživatele k zařízení."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO device_access (device_id, user_id, can_edit)
        VALUES (?, ?, ?)
        ON CONFLICT(device_id, user_id) DO UPDATE SET can_edit = excluded.can_edit
    """, (int(device_id), int(user_id), int(can_edit)))
    conn.commit()
    conn.close()


def odeber_pristup_zarizeni(device_id: int, user_id: int):
    """Odebere přístup uživatele k zařízení."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM device_access WHERE device_id = ? AND user_id = ?",
              (int(device_id), int(user_id)))
    conn.commit()
    conn.close()


def dej_pristupy_zarizeni(device_id: int):
    """Vrátí seznam uživatelů s přístupem k zařízení (kromě vlastníka)."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT da.access_id, da.user_id, u.name, u.surname, u.login, da.can_edit, da.assigned
        FROM device_access da
        JOIN users u ON da.user_id = u.user_id
        WHERE da.device_id = ?
        ORDER BY da.assigned
    """, (int(device_id),))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def ma_pristup_k_zarizeni(device_id: int, user_id: int, is_admin: bool) -> bool:
    """Vrátí True, pokud má uživatel právo vidět zařízení."""
    if is_admin:
        return True
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT 1 FROM devices WHERE device_id = ? AND user_id = ?
        UNION
        SELECT 1 FROM device_access WHERE device_id = ? AND user_id = ?
    """, (int(device_id), int(user_id), int(device_id), int(user_id)))
    result = c.fetchone()
    conn.close()
    return result is not None


def muze_editovat_zarizeni(device_id: int, user_id: int, is_admin: bool) -> bool:
    """Vrátí True, pokud má uživatel právo editovat zařízení."""
    if is_admin:
        return True
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT 1 FROM devices WHERE device_id = ? AND user_id = ?
        UNION
        SELECT 1 FROM device_access WHERE device_id = ? AND user_id = ? AND can_edit = 1
    """, (int(device_id), int(user_id), int(device_id), int(user_id)))
    result = c.fetchone()
    conn.close()
    return result is not None


_PREHLED_SELECT = """
    SELECT
        d.device_id, d.client_id, d.location, d.description,
        (SELECT COUNT(*) FROM messages m WHERE m.device_id = d.device_id) AS total_trains,
        (SELECT COUNT(*) FROM messages m WHERE m.device_id = d.device_id
           AND m.assigned >= datetime('now', '-7 days')) AS trains_week,
        (SELECT m.assigned FROM messages m WHERE m.device_id = d.device_id
           ORDER BY m.message_id DESC LIMIT 1) AS last_train_time,
        (SELECT dc.temperature FROM device_conditions dc WHERE dc.device_id = d.device_id
           ORDER BY dc.condition_id DESC LIMIT 1) AS temperature,
        (SELECT dc.humidity FROM device_conditions dc WHERE dc.device_id = d.device_id
           ORDER BY dc.condition_id DESC LIMIT 1) AS humidity,
        (SELECT dc.batt_mv FROM device_conditions dc WHERE dc.device_id = d.device_id
           ORDER BY dc.condition_id DESC LIMIT 1) AS batt_mv,
        (SELECT dc.signal_strength FROM device_conditions dc WHERE dc.device_id = d.device_id
           ORDER BY dc.condition_id DESC LIMIT 1) AS signal_strength,
        (SELECT dc.received_at FROM device_conditions dc WHERE dc.device_id = d.device_id
           ORDER BY dc.condition_id DESC LIMIT 1) AS conditions_at
    FROM devices d
"""


def dej_prehled_pro_uzivatele(user_id: int, is_admin: bool):
    """Jako dej_prehled_zarizeni, ale filtruje dle přístupových práv."""
    conn = get_db_connection()
    c = conn.cursor()
    if is_admin:
        c.execute(_PREHLED_SELECT + " ORDER BY CAST(d.client_id AS INTEGER), d.client_id")
    else:
        c.execute(
            _PREHLED_SELECT +
            " WHERE d.device_id IN ("
            "   SELECT device_id FROM devices WHERE user_id = ?"
            "   UNION"
            "   SELECT device_id FROM device_access WHERE user_id = ?"
            " ) ORDER BY CAST(d.client_id AS INTEGER), d.client_id",
            (int(user_id), int(user_id))
        )
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def dej_seznam_zprav(id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
              SELECT message_id, messages.assigned, packets, filename,
                     train_type, speed_kmh, damage_detected, measured_at
              FROM messages
              JOIN devices ON messages.device_id = devices.device_id
              WHERE messages.device_id = ?
              ORDER BY COALESCE(measured_at, messages.assigned) DESC""", (int(id),))
    rows = c.fetchall()
    conn.close()
    return [
        {
            "message_id": r[0],
            "assigned": r[1],
            "packets": r[2],
            "filename": r[3],
            "train_type": r[4],
            "speed_kmh": r[5],
            "damage_detected": r[6],
            "measured_at": r[7],
        }
        for r in rows
    ]


def dej_zprava_filename(message_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT filename FROM messages WHERE message_id = ?", (int(message_id),))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def dej_zprava_info(message_id: int):
    """Vrátí device_id a filename záznamu, nebo None."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT device_id, filename FROM messages WHERE message_id = ?", (int(message_id),))
    row = c.fetchone()
    conn.close()
    return {"device_id": row[0], "filename": row[1]} if row else None


def smaz_zpravu(message_id: int) -> str | None:
    """Smaže záznam z DB a vrátí cestu k bin souboru (nebo None pokud neexistoval)."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT filename FROM messages WHERE message_id = ?", (int(message_id),))
    row = c.fetchone()
    if not row:
        conn.close()
        return None
    filename = row[0]
    c.execute("DELETE FROM messages WHERE message_id = ?", (int(message_id),))
    conn.commit()
    conn.close()
    return filename




def ensure_classification_columns():
    """Přidá klasifikační sloupce do tabulky messages, pokud ještě neexistují."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("PRAGMA table_info(messages)")
    existing = {row[1] for row in c.fetchall()}
    new_columns = {
        "train_type": "TEXT",
        "speed_kmh": "REAL",
        "damage_detected": "INTEGER",
        "classified_at": "TEXT",
    }
    for col, col_type in new_columns.items():
        if col not in existing:
            c.execute(f"ALTER TABLE messages ADD COLUMN {col} {col_type}")
    conn.commit()
    conn.close()


def ensure_conditions_table():
    """Vytvoří tabulku device_conditions, pokud neexistuje."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS device_conditions (
            condition_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id      INTEGER NOT NULL,
            received_at    TEXT NOT NULL,
            temperature    REAL,
            humidity       REAL,
            pressure       REAL,
            batt_mv        INTEGER,
            signal_strength INTEGER,
            uptime_minutes  INTEGER,
            train_counter   INTEGER,
            FOREIGN KEY (device_id) REFERENCES devices(device_id)
        )
    """)
    conn.commit()
    conn.close()


def uloz_podmínky(p: dict):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO device_conditions
            (device_id, received_at, temperature, humidity, pressure,
             batt_mv, signal_strength, uptime_minutes, train_counter)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        p["device_id"],
        datetime.now().isoformat(timespec="seconds"),
        p["temperature"],
        p["humidity"],
        p["pressure"],
        p["batt_mv"],
        p["signal_strength"],
        p["uptime_minutes"],
        p["train_counter"],
    ))
    conn.commit()
    conn.close()


def dej_posledni_podmínky(device_id: int):
    """Vrátí poslední zaznamenanou telemetrii pro zařízení."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT received_at, temperature, humidity, pressure,
               batt_mv, signal_strength, uptime_minutes, train_counter
        FROM device_conditions
        WHERE device_id = ?
        ORDER BY condition_id DESC LIMIT 1
    """, (int(device_id),))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def dej_historii_podmínek(device_id: int, limit: int = 50):
    """Vrátí historii telemetrie pro zařízení (nejnovější první)."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT received_at, temperature, humidity, pressure,
               batt_mv, signal_strength, uptime_minutes, train_counter
        FROM device_conditions
        WHERE device_id = ?
        ORDER BY condition_id DESC LIMIT ?
    """, (int(device_id), limit))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]
    
    
    
    
def print_packet_content (incomming_packet):
    print("packet header: %x" % incomming_packet.packet_header)
    print("packet version: %04x" % incomming_packet.packet_version)
    print("actual packet NR: %d" % incomming_packet.actual_packet_nr)
    print("total packet to recieve: %d" % incomming_packet.total_packet_nr)
    print("total samples measured: %d" % incomming_packet.total_sample_count)
    print("packet timestamp unix: %d" % incomming_packet.timestamp)
    
    readable_time = datetime.fromtimestamp(incomming_packet.timestamp)
    
    print("packet timestamp HRF: %s" % (readable_time.strftime('%Y-%m-%d %H:%M:%S')))
    print("signals series length %d" % WAVE_SAMPLE_LEN)
    print("train count uint16 value: %d" % incomming_packet.train_counter)
    print("CRC value: %04x" % incomming_packet.CRC)
    print("")
    print("--signal data content--")
    print("chanel 0 voltages:  %s" % ', '.join(map(str, incomming_packet.chan_0_vlt)))
    print("chanel 0 integral:  %s" % ', '.join(map(str, incomming_packet.chan_0_int)))
    print("chanel 1 voltages:  %s" % ', '.join(map(str, incomming_packet.chan_1_vlt)))
    print("chanel 1 integral:  %s" % ', '.join(map(str, incomming_packet.chan_1_int)))

        