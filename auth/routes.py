from flask import Blueprint, render_template, redirect, request, flash, current_app, url_for,jsonify
from flask_login import login_user, logout_user, login_required, current_user
import sqlite3
from werkzeug.security import generate_password_hash
from instance import data_funkce
from auth.models import User,load_labels
from decorators import ma_roli

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        login_name = request.form['username']
        password = request.form['password']
        user_row = data_funkce.is_user(login_name)
        if not user_row:
            flash(load_labels(lang="cz")["uzivatel_nenalezen"], 'danger')
            return redirect(url_for('auth.login'))

        user_id, name, surname = user_row
        if data_funkce.pass_ok(user_id,password):
            user = User(user_id, login_name, name, surname)
            login_user(user)
            return redirect(url_for('auth.dashboard'))
        else:
            flash(load_labels(lang="cz")["neplatne_heslo"], 'danger')
            return redirect(url_for('auth.login'))

    return render_template("login.html",labels=load_labels(lang="eng"))

@auth_bp.route("/check-login", methods=["POST"])
def check_login():

    login = request.json.get("login", "").strip()
    exists = data_funkce.login_check(login)  # ⬅️ zachytíme výsledek

    return jsonify({"exists": exists})

@auth_bp.route("/logout")
@login_required
def logout():
   
    logout_user()
    return redirect(url_for('auth.login'))


@auth_bp.route("/users", methods=["get","post"])
@login_required
@ma_roli("admin")
def users():
    if request.method == 'POST':
        data_funkce.uloz_uzivatele(request.form)
        
    users=data_funkce.seznam_uzivatelu()
    return render_template("users.html", user=current_user,users=users,labels=load_labels(lang="eng"))


@auth_bp.route("/user/<id>", methods=["get", "post"])
@login_required
def user_detail(id):
    labels=load_labels(lang="eng")
    if request.method == "POST":
        if "new_role" in request.form:
            role_id = request.form.get("role")  # předpokládám, že ve formu máš <select name="role_id"> nebo <input name="role_id">
            if role_id:
                success = data_funkce.pridej_roli(id, role_id)
                if success:
                    flash(labels["flash_role_pridana"], "success")
                else:
                    flash(labels["flash_role_duplicita"], "warning")
            else:
                flash("Nebyla vybrána žádná role.", "danger")
        if "zmen_uzivatele" in request.form:
            data_funkce.zmen_uzivatele(id,request.form)
        if "nove_heslo" in request.form:
            data_funkce.zmen_heslo(id,request.form)
        
        # Můžeš sem přidat i jiné submity (např. změna hesla) podle potřeby

        if "remove_role" in request.form:
            user_role_id = request.form.get("user_role_id")
            if user_role_id:
                # Zjisti detail této role (user_id, role_id)
                detail = data_funkce.dej_user_role_detail(user_role_id)
                print(detail)
                if detail:
                    role_id = detail["role_id"]
                    target_user_id = detail["user_id"]

                    if role_id == 1:  # 1 = admin role_id, uprav dle DB

                        # Kontrola: není poslední admin?
                        admin_count = data_funkce.pocet_adminu()
                        print(admin_count)
                        if admin_count <= 1:
                            flash("Nelze odebrat roli administrátora poslednímu aktivnímu administrátorovi.", "danger")
                            return redirect(url_for("auth.user_detail", id=id))

                        # Kontrola: nesmaže sám sobě admina
                        if str(target_user_id) == str(current_user.id):
                            flash("Nemůžete sám sobě odebrat roli administrátora.", "danger")
                            return redirect(url_for("auth.user_detail", id=id))

                    # Pokud vše OK, odeber roli
                    if data_funkce.odeber_roli(user_role_id):
                        flash("Role byla odebrána.", "success")
                    else:
                        flash("Odebrání role se nezdařilo.", "danger")
                else:
                    flash("Role nebyla nalezena.", "danger")
            else:
                flash("Nastala chyba při odebírání role.", "danger")

        return redirect(url_for("auth.user_detail", id=id))

    user_detail = data_funkce.dej_detail_uzivatele(id)
    if user_detail:
        return render_template(
            "user_detail.html",
            user=current_user,
            data=user_detail,
            roles=data_funkce.seznam_roli(),
            labels=load_labels(lang="cz")
        )
    else:
        flash("Přistupujete k neexistujícímu uživateli.", "warning")
        return redirect(url_for("auth.users"))
