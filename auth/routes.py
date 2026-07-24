import time
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from instance import data_funkce
from auth.models import User, load_labels
from decorators import require_login, ma_roli
from helpers import flash, templates, template_context

auth_router = APIRouter(prefix="/auth")

# ── Rate-limiting neúspěšných přihlášení ──
# In-memory (per proces, nepersistuje restart) — po _MAX_ATTEMPTS chybných
# pokusech na stejné přihlašovací jméno se login na _LOCKOUT_SECONDS zamkne.
_LOGIN_ATTEMPTS: dict[str, dict] = {}
_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 60


def _login_locked_for(login_name: str) -> int:
    """Vrátí počet zbývajících sekund uzamčení (0 = není zamčeno)."""
    entry = _LOGIN_ATTEMPTS.get(login_name)
    if not entry:
        return 0
    remaining = entry["locked_until"] - time.monotonic()
    return max(0, int(remaining))


def _login_register_failure(login_name: str):
    entry = _LOGIN_ATTEMPTS.setdefault(login_name, {"count": 0, "locked_until": 0.0})
    entry["count"] += 1
    if entry["count"] >= _MAX_ATTEMPTS:
        entry["locked_until"] = time.monotonic() + _LOCKOUT_SECONDS
        entry["count"] = 0


def _login_register_success(login_name: str):
    _LOGIN_ATTEMPTS.pop(login_name, None)


@auth_router.get("/login")
async def login_get(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/auth/dashboard", status_code=302)
    return templates.TemplateResponse(request, "login.html", context=template_context(request, labels=load_labels(lang="eng")))


@auth_router.post("/login")
async def login_post(request: Request):
    form = await request.form()
    login_name = form.get("username", "")
    password = form.get("password", "")

    zbyva = _login_locked_for(login_name)
    if zbyva:
        flash(request, f"Příliš mnoho neúspěšných pokusů o přihlášení. Zkuste to znovu za {zbyva} s.", "danger")
        return RedirectResponse(url="/auth/login", status_code=302)

    user_row = data_funkce.is_user(login_name)
    if not user_row:
        _login_register_failure(login_name)
        flash(request, load_labels(lang="cz")["uzivatel_nenalezen"], "danger")
        return RedirectResponse(url="/auth/login", status_code=302)

    user_id, name, surname = user_row
    if data_funkce.pass_ok(user_id, password):
        _login_register_success(login_name)
        request.session["user_id"] = user_id
        request.session["login"] = login_name
        return RedirectResponse(url="/auth/dashboard", status_code=302)
    else:
        _login_register_failure(login_name)
        flash(request, load_labels(lang="cz")["neplatne_heslo"], "danger")
        return RedirectResponse(url="/auth/login", status_code=302)


@auth_router.post("/check-login")
async def check_login(request: Request):
    body = await request.json()
    login = body.get("login", "").strip()
    exists = data_funkce.login_check(login)
    return JSONResponse({"exists": exists})


@auth_router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=302)


@auth_router.post("/change-password")
async def change_password(request: Request, current_user: User = Depends(require_login)):
    form = await request.form()
    stare_heslo = form.get("stare_heslo", "")
    nove_heslo  = form.get("heslo", "")
    potvrz      = form.get("heslo2", "")

    if not nove_heslo or nove_heslo != potvrz:
        flash(request, "Nové heslo se neshoduje s potvrzením.", "danger")
        return RedirectResponse(url="/auth/dashboard", status_code=302)

    if not data_funkce.pass_ok(current_user.id, stare_heslo):
        flash(request, "Stávající heslo není správné.", "danger")
        return RedirectResponse(url="/auth/dashboard", status_code=302)

    data_funkce.zmen_heslo(current_user.id, {"heslo": nove_heslo})
    flash(request, "Heslo bylo úspěšně změněno.", "success")
    return RedirectResponse(url="/auth/dashboard", status_code=302)


@auth_router.get("/users")
async def users_get(request: Request, current_user: User = Depends(ma_roli("admin"))):
    user_list = data_funkce.seznam_uzivatelu()
    return templates.TemplateResponse(
        request, "users.html",
        context=template_context(request, current_user=current_user, users=user_list, labels=load_labels(lang="cz"))
    )


@auth_router.post("/users")
async def users_post(request: Request, current_user: User = Depends(ma_roli("admin"))):
    form = await request.form()
    data_funkce.uloz_uzivatele(form)
    return RedirectResponse(url="/auth/users", status_code=302)


@auth_router.get("/user/{id}")
async def user_detail_get(id: str, request: Request, current_user: User = Depends(ma_roli("admin"))):
    labels = load_labels(lang="cz")
    user_data = data_funkce.dej_detail_uzivatele(id)
    if user_data:
        return templates.TemplateResponse(
            request, "user_detail.html",
            context=template_context(
                request,
                current_user=current_user,
                data=user_data,
                roles=data_funkce.seznam_roli(),
                labels=labels,
            )
        )
    flash(request, "Přistupujete k neexistujícímu uživateli.", "warning")
    return RedirectResponse(url="/auth/users", status_code=302)


@auth_router.post("/user/{id}")
async def user_detail_post(id: str, request: Request, current_user: User = Depends(ma_roli("admin"))):
    labels = load_labels(lang="cz")
    form = await request.form()

    if "new_role" in form:
        role_id = form.get("role")
        if role_id:
            success = data_funkce.pridej_roli(id, role_id)
            if success:
                flash(request, labels["flash_role_pridana"], "success")
            else:
                flash(request, labels["flash_role_duplicita"], "warning")
        else:
            flash(request, "Nebyla vybrána žádná role.", "danger")

    if "zmen_uzivatele" in form:
        data_funkce.zmen_uzivatele(id, form)

    if "nove_heslo" in form:
        data_funkce.zmen_heslo(id, form)

    if "remove_role" in form:
        user_role_id = form.get("user_role_id")
        if user_role_id:
            detail = data_funkce.dej_user_role_detail(user_role_id)
            if detail:
                role_id = detail["role_id"]
                target_user_id = detail["user_id"]

                if role_id == 1:
                    admin_count = data_funkce.pocet_adminu()
                    if admin_count <= 1:
                        flash(request, "Nelze odebrat roli administrátora poslednímu aktivnímu administrátorovi.", "danger")
                        return RedirectResponse(url=f"/auth/user/{id}", status_code=302)

                    if str(target_user_id) == str(current_user.id):
                        flash(request, "Nemůžete sám sobě odebrat roli administrátora.", "danger")
                        return RedirectResponse(url=f"/auth/user/{id}", status_code=302)

                if data_funkce.odeber_roli(user_role_id):
                    flash(request, "Role byla odebrána.", "success")
                else:
                    flash(request, "Odebrání role se nezdařilo.", "danger")
            else:
                flash(request, "Role nebyla nalezena.", "danger")
        else:
            flash(request, "Nastala chyba při odebírání role.", "danger")

    return RedirectResponse(url=f"/auth/user/{id}", status_code=302)

