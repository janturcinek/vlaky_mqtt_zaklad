import os
import re
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from auth.models import User, load_labels
from decorators import require_login
from helpers import templates, template_context
from app_logger import LOG_FILE

admin_router = APIRouter(prefix="/auth/admin")

_ENTRY_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(\w+)\] ([^:]+): (.*)$"
)


def _load_log_entries(max_entries: int = 200) -> list[dict]:
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        raw = f.read()

    blocks: list[str] = []
    current: list[str] = []
    for line in raw.splitlines(keepends=True):
        if _ENTRY_RE.match(line) and current:
            blocks.append("".join(current).rstrip())
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append("".join(current).rstrip())

    entries: list[dict] = []
    for block in blocks:
        lines = block.splitlines()
        m = _ENTRY_RE.match(lines[0]) if lines else None
        if m:
            traceback = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
            entries.append({
                "ts":        m.group(1),
                "level":     m.group(2),
                "source":    m.group(3).strip(),
                "message":   m.group(4).strip(),
                "traceback": traceback,
            })
        else:
            entries.append({
                "ts": "", "level": "INFO", "source": "",
                "message": block, "traceback": "",
            })

    entries.reverse()
    return entries[:max_entries]


@admin_router.get("/error-log")
async def error_log_view(request: Request, current_user: User = Depends(require_login)):
    if not current_user.admin:
        return RedirectResponse(url="/auth/dashboard", status_code=302)
    entries = _load_log_entries()
    return templates.TemplateResponse(
        request, "error_log.html",
        context=template_context(request, current_user,
                                 title="Chybový log",
                                 log_entries=entries,
                                 log_file=LOG_FILE,
                                 labels=load_labels(lang="cz")),
    )


@admin_router.post("/error-log/clear")
async def error_log_clear(request: Request, current_user: User = Depends(require_login)):
    if not current_user.admin:
        return RedirectResponse(url="/auth/dashboard", status_code=302)
    if os.path.exists(LOG_FILE):
        open(LOG_FILE, "w", encoding="utf-8").close()
    return RedirectResponse(url="/auth/admin/error-log", status_code=302)
