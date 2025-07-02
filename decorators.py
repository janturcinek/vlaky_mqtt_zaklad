# /decorators.py
from functools import wraps
from flask import current_app, abort,redirect,url_for
from instance import data_funkce
from flask_login import current_user

def ma_roli(role):
    """
    Dekorátor pro kontrolu, zda má aktuální uživatel dané právo.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if not data_funkce.ma_roli(current_user.id,role):
                return redirect(url_for('auth.login'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


