# /decorators.py
from fastapi import Request, Depends
from instance import data_funkce
from auth.models import load_user


class NotAuthenticatedException(Exception):
    pass


class NotAuthorizedException(Exception):
    pass


def get_current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return load_user(user_id)


def require_login(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise NotAuthenticatedException()
    user = load_user(user_id)
    if not user:
        raise NotAuthenticatedException()
    return user


def ma_roli(role: str):
    """
    Dependency factory pro kontrolu, zda má aktuální uživatel danou roli.
    Použití: user = Depends(ma_roli("admin"))
    """
    def dependency(request: Request):
        user_id = request.session.get("user_id")
        if not user_id:
            raise NotAuthenticatedException()
        user = load_user(user_id)
        if not user:
            raise NotAuthenticatedException()
        if not data_funkce.ma_roli(user.id, role):
            raise NotAuthorizedException()
        return user
    return dependency

