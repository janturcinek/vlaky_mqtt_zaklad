import os
import sqlite3
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from instance import data_funkce
from auth.models import User, load_labels
from decorators import require_login
from helpers import templates, template_context, flash
import classifier as clf  # noqa: E402
from mqtt_receiver import recent_messages

device_router = APIRouter(prefix="/auth")


@device_router.get("/dashboard")
async def dashboard(request: Request, current_user: User = Depends(require_login)):
    prehled = data_funkce.dej_prehled_pro_uzivatele(current_user.id, current_user.admin)
    return templates.TemplateResponse(
        request, "dashboard.html",
        context=template_context(request, current_user=current_user,
                                 prehled=prehled, labels=load_labels(lang="cz"))
    )


@device_router.get("/devices")
async def devices_get(request: Request, current_user: User = Depends(require_login),
                      prefill_client_id: str = ""):
    device_list = data_funkce.dej_seznam_zarizeni_pro_uzivatele(current_user.id, current_user.admin)
    return templates.TemplateResponse(
        request, "devices.html",
        context=template_context(request, current_user=current_user,
                                 devices=device_list, labels=load_labels(lang="cz"),
                                 prefill_client_id=prefill_client_id)
    )


@device_router.post("/devices")
async def devices_post(request: Request, current_user: User = Depends(require_login)):
    form = await request.form()
    if "pridej_zarizeni" in form:
        try:
            data_funkce.pridej_zarizeni(current_user.id, form)
            flash(request, f"Zařízení '{form['oznaceni']}' bylo přidáno.", "success")
        except sqlite3.IntegrityError:
            flash(request, f"Zařízení s Client ID '{form['oznaceni']}' již existuje.", "danger")
    return RedirectResponse(url="/auth/devices", status_code=302)


@device_router.get("/devices/manage/{id}")
async def manage_device_get(id: str, request: Request, current_user: User = Depends(require_login)):
    if not data_funkce.muze_editovat_zarizeni(int(id), current_user.id, current_user.admin):
        flash(request, "Nemáte oprávnění upravovat toto zařízení.", "danger")
        return RedirectResponse(url="/auth/dashboard", status_code=302)
    device = data_funkce.dej_zarizeni(id)
    pristupy = data_funkce.dej_pristupy_zarizeni(int(id))
    vsichni = data_funkce.seznam_uzivatelu()
    # vyfiltruj vlastníka a uživatele, kteří přístup už mají
    pristup_ids = {p["user_id"] for p in pristupy}
    device_owner_id = None
    try:
        conn_tmp = data_funkce.get_db_connection()
        row = conn_tmp.execute("SELECT user_id FROM devices WHERE device_id=?", (int(id),)).fetchone()
        conn_tmp.close()
        if row:
            device_owner_id = row[0]
    except Exception:
        pass
    dostupni = [u for u in vsichni if u[0] != device_owner_id and u[0] not in pristup_ids]
    return templates.TemplateResponse(
        request, "manage_device.html",
        context=template_context(request, current_user=current_user, data=device,
                                 pristupy=pristupy, dostupni_uziv=dostupni,
                                 labels=load_labels(lang="cz"))
    )


@device_router.post("/devices/manage/{id}")
async def manage_device_post(id: str, request: Request, current_user: User = Depends(require_login)):
    if not data_funkce.muze_editovat_zarizeni(int(id), current_user.id, current_user.admin):
        return RedirectResponse(url="/auth/dashboard", status_code=302)
    form = await request.form()
    if "uprav_zarizeni" in form:
        data_funkce.uprav_zarizeni(id, form)
        flash(request, "Zařízení bylo upraveno.", "success")
    elif "pridej_pristup" in form:
        uid = form.get("pristup_user_id", "")
        can_edit = 1 if form.get("pristup_can_edit") else 0
        if uid:
            data_funkce.pridej_pristup_zarizeni(int(id), int(uid), can_edit)
            flash(request, "Přístup byl přidán.", "success")
    elif "odeber_pristup" in form:
        uid = form.get("odeber_user_id", "")
        if uid:
            data_funkce.odeber_pristup_zarizeni(int(id), int(uid))
            flash(request, "Přístup byl odebrán.", "success")
    return RedirectResponse(url=f"/auth/devices/manage/{id}", status_code=302)


@device_router.get("/devices/data/{id}")
async def device_data(id: str, request: Request, current_user: User = Depends(require_login)):
    if not data_funkce.ma_pristup_k_zarizeni(int(id), current_user.id, current_user.admin):
        flash(request, "Nemáte oprávnění zobrazit data tohoto zařízení.", "danger")
        return RedirectResponse(url="/auth/dashboard", status_code=302)
    zpravy = data_funkce.dej_seznam_zprav(id)
    device = data_funkce.dej_zarizeni(id)
    posledni = data_funkce.dej_posledni_podmínky(int(id))
    if posledni is not None:
        posledni["train_counter"] = data_funkce.dej_pocet_zprav_zarizeni(int(id))
    historie = data_funkce.dej_historii_podmínek(int(id), limit=50)
    muze_edit = data_funkce.muze_editovat_zarizeni(int(id), current_user.id, current_user.admin)
    return templates.TemplateResponse(
        request, "device_data.html",
        context=template_context(request, current_user=current_user,
                                  zpravy=zpravy, device=device,
                                  posledni_podmínky=posledni,
                                  historie_podmínek=historie,
                                  muze_edit=muze_edit,
                                  labels=load_labels(lang="cz"))
    )


@device_router.get("/api/message/{message_id}/waveform")
async def message_waveform(message_id: int, request: Request,
                            current_user: User = Depends(require_login)):
    filename = data_funkce.dej_zprava_filename(message_id)
    if not filename:
        return JSONResponse({"error": "zpráva nenalezena"}, status_code=404)

    filepath = os.path.join(os.getcwd(), filename)
    if not os.path.exists(filepath):
        return JSONResponse({"error": "soubor nenalezen"}, status_code=404)

    try:
        t, ch0_int, ch0_vlt, ch1_int, ch1_vlt, peaks_t = clf.get_waveform_data(filepath)
        return JSONResponse({
            "time":    t,
            "ch0_int": ch0_int,
            "ch0_vlt": ch0_vlt,
            "ch1_int": ch1_int,
            "ch1_vlt": ch1_vlt,
            "peaks":   peaks_t,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@device_router.post("/api/message/{message_id}/classify")
async def message_classify(message_id: int, request: Request,
                            current_user: User = Depends(require_login)):
    filename = data_funkce.dej_zprava_filename(message_id)
    if not filename:
        return JSONResponse({"error": "zpráva nenalezena"}, status_code=404)

    filepath = os.path.join(os.getcwd(), filename)
    if not os.path.exists(filepath):
        return JSONResponse({"error": "soubor nenalezen"}, status_code=404)

    try:
        result = clf.classify_bin_file(filepath)
        data_funkce.uloz_klasifikaci(
            message_id,
            result["typ_vlaku"],
            result["rychlost_kmh"],
            result["poskozeni_podvozku"],
        )
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@device_router.get("/stats")
async def stats():
    devices = data_funkce.dej_pocet_zarizeni()
    packets = data_funkce.celkem_paketu()
    last_message = data_funkce.posledni_zprava()
    return JSONResponse({
        "devices": devices,
        "packets": packets,
        "last_message": list(last_message) if last_message else None
    })


@device_router.get("/api/mqtt-log")
async def mqtt_log(current_user: User = Depends(require_login)):
    return JSONResponse(list(recent_messages))


# ── Správa typů vlaků ────────────────────────────────────────────────────────

def _require_admin(current_user: User):
    if not current_user.admin:
        return False
    return True


@device_router.get("/train-types")
async def train_types_get(request: Request, current_user: User = Depends(require_login)):
    if not current_user.admin:
        flash(request, "Přístup pouze pro administrátory.", "danger")
        return RedirectResponse(url="/auth/dashboard", status_code=302)
    typy = data_funkce.dej_seznam_typu_vlaku()
    return templates.TemplateResponse(
        request, "train_types.html",
        context=template_context(request, current_user=current_user,
                                 typy=typy, editovany=None, labels=load_labels(lang="cz"))
    )


@device_router.post("/train-types")
async def train_types_post(request: Request, current_user: User = Depends(require_login)):
    if not current_user.admin:
        return RedirectResponse(url="/auth/dashboard", status_code=302)
    form = await request.form()
    if "pridej_typ" in form:
        try:
            data_funkce.pridej_typ_vlaku(
                form["typ"], float(form["pomer"]), int(form["dvojkoli_mm"]), form.get("popis", "")
            )
            flash(request, f"Typ '{form['typ']}' byl přidán.", "success")
        except sqlite3.IntegrityError:
            flash(request, f"Typ '{form['typ']}' již existuje.", "danger")
    return RedirectResponse(url="/auth/train-types", status_code=302)


@device_router.get("/train-types/edit/{ttid}")
async def train_type_edit_get(ttid: int, request: Request, current_user: User = Depends(require_login)):
    if not current_user.admin:
        return RedirectResponse(url="/auth/dashboard", status_code=302)
    typy = data_funkce.dej_seznam_typu_vlaku()
    editovany = data_funkce.dej_typ_vlaku(ttid)
    return templates.TemplateResponse(
        request, "train_types.html",
        context=template_context(request, current_user=current_user,
                                 typy=typy, editovany=editovany, labels=load_labels(lang="cz"))
    )


@device_router.post("/train-types/edit/{ttid}")
async def train_type_edit_post(ttid: int, request: Request, current_user: User = Depends(require_login)):
    if not current_user.admin:
        return RedirectResponse(url="/auth/dashboard", status_code=302)
    form = await request.form()
    if "uloz_typ" in form:
        try:
            data_funkce.uprav_typ_vlaku(
                ttid, form["typ"], float(form["pomer"]), int(form["dvojkoli_mm"]), form.get("popis", "")
            )
            flash(request, f"Typ '{form['typ']}' byl upraven.", "success")
        except sqlite3.IntegrityError:
            flash(request, f"Název '{form['typ']}' je již použit.", "danger")
            return RedirectResponse(url=f"/auth/train-types/edit/{ttid}", status_code=302)
    return RedirectResponse(url="/auth/train-types", status_code=302)


@device_router.post("/train-types/delete/{ttid}")
async def train_type_delete(ttid: int, request: Request, current_user: User = Depends(require_login)):
    if not current_user.admin:
        return RedirectResponse(url="/auth/dashboard", status_code=302)
    data_funkce.smaz_typ_vlaku(ttid)
    flash(request, "Typ byl odstraněn.", "success")
    return RedirectResponse(url="/auth/train-types", status_code=302)
