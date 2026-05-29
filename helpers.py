# helpers.py – náhrada za Flask flash messages
from fastapi import Request
from fastapi.templating import Jinja2Templates
import os

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def flash(request: Request, message: str, category: str = "info"):
    """Uloží flash zprávu do session."""
    msgs = list(request.session.get("_messages", []))
    msgs.append({"message": message, "category": category})
    request.session["_messages"] = msgs


def get_flashed_messages(request: Request):
    """Načte a vymaže flash zprávy ze session. Vrátí list (category, message) tuplů."""
    msgs = list(request.session.get("_messages", []))
    request.session["_messages"] = []
    return [(m["category"], m["message"]) for m in msgs]


def template_context(request: Request, current_user=None, **kwargs):
    """Sestaví standardní kontext pro šablonu (bez request – ten jde jako 1. arg TemplateResponse)."""
    return {
        "current_user": current_user,
        "flashed_messages": get_flashed_messages(request),
        **kwargs,
    }
