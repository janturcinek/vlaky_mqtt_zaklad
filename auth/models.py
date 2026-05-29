import sqlite3
from nastaveni import DevelopmentConfig
from instance import data_funkce
import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class User:
    def __init__(self, user_id, login, name, surname, admin=False):
        self.id = user_id
        self.login = login
        self.name = name
        self.surname = surname
        if not admin:
            admin = data_funkce.ma_roli(user_id, "admin")
        self.admin = admin

    @property
    def is_authenticated(self):
        return True

def load_user(user_id):
    conn = sqlite3.connect(DevelopmentConfig.DATABASE)
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
    langs_path = os.path.join(BASE_DIR, 'instance', 'langs.json')
    with open(langs_path, encoding='utf-8') as f:
        data = json.load(f)
    return {key: translations.get(lang, key) for key, translations in data.items()}