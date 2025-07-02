
from flask import Blueprint, render_template, session, redirect, request

mqtt_bp = Blueprint('mqtt', __name__)



@mqtt_bp.route("/users", methods=["GET", "POST"])
def users():
    if "user" not in session:
        return redirect("/auth/login")
    if request.method == "POST":
        username = request.form.get("username")
        role = request.form.get("role")
        print(f"Nový uživatel: {username}, role: {role}")
    return render_template("users.html")

