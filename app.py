from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.requests import Request
from starlette.middleware.sessions import SessionMiddleware
import threading
import sqlite3

from mqtt_receiver import run_mqtt_receiver
from nastaveni import DevelopmentConfig
from auth.routes import auth_router
from auth.devices import device_router
from decorators import NotAuthenticatedException, NotAuthorizedException
from werkzeug.security import generate_password_hash
from instance.data_funkce import ensure_classification_columns, ensure_conditions_table, ensure_device_access_table, ensure_train_types_table


def create_app() -> FastAPI:
    app = FastAPI()

    app.add_middleware(SessionMiddleware, secret_key=DevelopmentConfig.SECRET_KEY)

    import os
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    app.include_router(auth_router)
    app.include_router(device_router)

    # Handlery pro přesměrování při chybách autentizace
    @app.exception_handler(NotAuthenticatedException)
    async def not_authenticated_handler(request: Request, exc: NotAuthenticatedException):
        return RedirectResponse(url="/auth/login", status_code=302)

    @app.exception_handler(NotAuthorizedException)
    async def not_authorized_handler(request: Request, exc: NotAuthorizedException):
        return RedirectResponse(url="/auth/login", status_code=302)

    @app.get("/")
    async def root(request: Request):
        if request.session.get("user_id"):
            return RedirectResponse(url="/auth/dashboard", status_code=302)
        return RedirectResponse(url="/auth/login", status_code=302)

    # Jednorázový endpoint pro přidání uživatele
    @app.get("/add-user", response_class=HTMLResponse)
    async def add_user():
        login = 'admin'
        name = 'Admin'
        surname = 'Uživatel'
        raw_password = 'admin123'

        conn = sqlite3.connect(DevelopmentConfig.DATABASE)
        c = conn.cursor()

        c.execute("SELECT user_id FROM users WHERE login = ?", (login,))
        existing_user = c.fetchone()

        if existing_user:
            conn.close()
            return f"⚠️ Uživatel '{login}' už existuje s ID {existing_user[0]}"

        c.execute("INSERT INTO users (name, surname, login) VALUES (?, ?, ?)",
                  (name, surname, login))
        user_id = c.lastrowid

        password_hash = generate_password_hash(raw_password)
        c.execute("INSERT INTO user_passwords (user_id, password) VALUES (?, ?)",
                  (user_id, password_hash))

        # Přiřaď adminskou roli (role_id=1, sysid='admin')
        c.execute("SELECT role_id FROM system_roles WHERE sysid = 'admin' LIMIT 1")
        role_row = c.fetchone()
        if role_row:
            c.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)",
                      (user_id, role_row[0]))

        conn.commit()
        conn.close()
        return f"✅ Uživatel '{login}' vytvořen s heslem '{raw_password}' a rolí admin"

    mqtt_thread = threading.Thread(target=run_mqtt_receiver, daemon=True)
    mqtt_thread.start()

    ensure_classification_columns()
    ensure_conditions_table()
    ensure_device_access_table()
    ensure_train_types_table()

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=False)
