from flask import Blueprint, render_template, redirect, request, flash, current_app, url_for, jsonify
from flask_login import login_user, logout_user, login_required, current_user
import sqlite3
from werkzeug.security import generate_password_hash
from instance import data_funkce
from auth.models import User,load_labels
from decorators import ma_roli

device_bp = Blueprint('devices', __name__, url_prefix='/auth')



@device_bp.route("/dashboard")
@login_required
def dashboard():
    stats={}
    return render_template("dashboard.html", user=current_user,stats={},labels=load_labels(lang="cz"))



@device_bp.route("/devices", methods=["get","post"])
@login_required
def divices():
    if request.method=="POST":
        if "pridej_zarizeni" in request.form:
            data_funkce.pridej_zarizeni(current_user.id,request.form)
    devices=data_funkce.dej_seznam_zarizeni()
    return render_template("devices.html", user=current_user,devices=devices,labels=load_labels(lang="cz"))

@device_bp.route("/devices/manage/<id>", methods=["get","post"])
@login_required
def manage_divices(id):
    if request.method=="POST":
        if "uprav_zarizeni" in request.form:
            data_funkce.uprav_zarizeni(id,request.form)
    device=data_funkce.dej_zarizeni(id)
    return render_template("manage_device.html", user=current_user,data=device,labels=load_labels(lang="cz"))



@device_bp.route("/stats")
def stats():

    devices = data_funkce.dej_pocet_zarizeni()
    packets = data_funkce.celkem_paketu()
    last_message = data_funkce.posledni_zprava()

    return jsonify({
        "devices": devices,
        "packets": packets,
        "last_message": list(last_message)
    })