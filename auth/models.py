from flask_login import UserMixin
import sqlite3
from flask import current_app
from instance import data_funkce
import os
import json

class User(UserMixin):
    def __init__(self, user_id, login, name, surname,admin=False):
        self.id = user_id
        self.login = login
        self.name = name
        self.surname = surname
        if not admin:
            admin=data_funkce.ma_roli(user_id,"admin")
        self.admin=admin

def load_user(user_id):
    db_path = current_app.config['DATABASE']
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT user_id, login, name, surname FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    
    conn.close()

    if row:
        return User(*row)
    return None



def load_labels(lang='cz'):
    """
    Načte JSON z instance/langs.json a vrátí dict překladů pro zvolený jazyk
    """
    # Sestavení cesty k souboru
    langs_path = os.path.join(current_app.instance_path, 'langs.json')

    with open(langs_path, encoding='utf-8') as f:
        data = json.load(f)

    # Vrátí pouze hodnoty pro daný jazyk (např. cz)
    return {key: translations.get(lang, key) for key, translations in data.items()}