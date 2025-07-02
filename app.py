from flask import Flask, redirect, url_for, current_app
from flask_login import LoginManager, current_user
import threading
from mqtt_receiver import run_mqtt_receiver  # funkce, která spustí klienta
from nastaveni import DevelopmentConfig
from auth.routes import auth_bp
from auth.devices import device_bp
from auth.models import load_user
from werkzeug.security import generate_password_hash
from datetime import datetime
import os
import sqlite3  # ⬅️ chyběl import

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(DevelopmentConfig)

    # Login manager
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    # Načti uživatele
    login_manager.user_loader(load_user)

    # Blueprinty
    app.register_blueprint(auth_bp)
    app.register_blueprint(device_bp)

    # Root přesměrování
    @app.route("/")
    def root():
        if current_user.is_authenticated:
            return redirect(url_for('auth.dashboard'))
        return redirect(url_for('auth.login'))

    # Jednorázový endpoint pro přidání uživatele
    @app.route('/add-user')
    def add_user():
        login = 'admin'
        name = 'Admin'
        surname = 'Uživatel'
        raw_password = 'admin123'
        
        db_path = current_app.config['DATABASE']
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        # Zkontroluj, zda uživatel existuje
        c.execute("SELECT user_id FROM users WHERE login = ?", (login,))
        existing_user = c.fetchone()

        if existing_user:
            conn.close()
            return f"⚠️ Uživatel '{login}' už existuje s ID {existing_user[0]}"

        # Vlož uživatele
        c.execute("INSERT INTO users (name, surname, login) VALUES (?, ?, ?)",
                  (name, surname, login))
        user_id = c.lastrowid

        # Vlož heslo (hash)
        password_hash = generate_password_hash(raw_password)
        c.execute("INSERT INTO user_passwords (user_id, password) VALUES (?, ?)",
                  (user_id, password_hash))

        conn.commit()
        conn.close()
        return f"✅ Uživatel '{login}' vytvořen s heslem '{raw_password}'"

    mqtt_thread = threading.Thread(target=run_mqtt_receiver, args=(app,), daemon=True)
    mqtt_thread.start()
    
    return app

if __name__ == "__main__":
    create_app().run(debug=True)
