import os
import re
from datetime import datetime
from nastaveni import DevelopmentConfig

_LOG_DIR = os.path.join(os.path.dirname(DevelopmentConfig.DATABASE), "mqtt_logs")
_LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(\S+)\s*(.*)$")
_SAFE_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}\.log$")


def _today_path() -> str:
    os.makedirs(_LOG_DIR, exist_ok=True)
    return os.path.join(_LOG_DIR, datetime.now().strftime("%Y-%m-%d") + ".log")


def log_event(event_type: str, **kwargs) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    detail = "  ".join(f"{k}={v}" for k, v in kwargs.items())
    line = f"{ts}  {event_type:<12}  {detail}\n"
    try:
        with open(_today_path(), "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def list_log_files() -> list[dict]:
    if not os.path.isdir(_LOG_DIR):
        return []
    files = []
    for name in sorted(os.listdir(_LOG_DIR), reverse=True):
        if name.endswith(".log"):
            path = os.path.join(_LOG_DIR, name)
            size = os.path.getsize(path)
            files.append({
                "date": name[:-4],
                "filename": name,
                "size_kb": round(size / 1024, 1),
            })
    return files


def read_log_file(filename: str, max_entries: int = 500) -> list[dict] | None:
    if not _SAFE_NAME.fullmatch(filename):
        return None
    path = os.path.join(_LOG_DIR, filename)
    if not os.path.exists(path):
        return None
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            if not line:
                continue
            m = _LINE_RE.match(line)
            if m:
                entries.append({"ts": m.group(1), "type": m.group(2), "detail": m.group(3)})
            else:
                entries.append({"ts": "", "type": "RAW", "detail": line})
    entries.reverse()
    return entries[:max_entries]
