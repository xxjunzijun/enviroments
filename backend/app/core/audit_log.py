import json
import os
import re
from datetime import datetime
from typing import Any


LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "log")


def server_log_filename(ip: str) -> str:
    """Return a stable log filename for a server IP address."""
    safe_ip = re.sub(r'[\\/:*?"<>|]', "_", ip or "unknown")
    return f"{safe_ip}.log"


def server_log_path(ip: str) -> str:
    return os.path.join(LOG_DIR, server_log_filename(ip))


def write_server_log(ip: str, payload: dict[str, Any]) -> None:
    """Append a JSON line to backend/log/{ip}.log using local deployment time."""
    os.makedirs(LOG_DIR, exist_ok=True)
    payload = dict(payload)
    payload["ip"] = ip
    payload["time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = json.dumps(payload, ensure_ascii=False)
    with open(server_log_path(ip), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_json_lines(path: str, limit: int = 200) -> dict[str, Any]:
    if not os.path.exists(path):
        return {"total": 0, "logs": []}

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    total = len(lines)
    recent = list(reversed(lines[-limit:]))
    logs = []
    for raw in recent:
        raw = raw.strip()
        if raw:
            try:
                logs.append(json.loads(raw))
            except Exception:
                logs.append({"raw": raw})

    return {"total": total, "logs": logs}
