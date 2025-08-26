import sqlite3
from flask import current_app
from werkzeug.security import generate_password_hash,check_password_hash
from nastaveni import WAVE_SAMPLE_LEN
from datetime import datetime

def get_db_connection():
    """Vytvoří připojení k databázi na základě Flask konfigurace"""
    db_path = current_app.config['DATABASE']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # volitelné: usnadní práci s výsledky
    return conn

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

def uloz_zpravu(device_id, topic, total_packets, filename):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO messages (device_id, topic, packets, filename) VALUES (?, ?, ?, ?)",
            (device_id, topic, total_packets, filename)
        )
        conn.commit()
    except Exception as e:
         print("nepodařilo se uložit z následujícího důvodu: ",e)
    conn.close()
    
def dej_seznam_zprav(id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
              SELECT messages.assigned, packets, filename from 
              messages join devices on messages.device_id=devices.device_id 
              where messages.device_id = ? """, (int(id),))
    
    result = c.fetchall()
    print(result)
    conn.close()
    return result
    
    
    
    
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

        