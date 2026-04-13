import os
import json
from fastapi import APIRouter, HTTPException, Query
from app.core.scheduler import LOG_DIR

router = APIRouter(prefix="/servers/{server_id}/logs", tags=["logs"])


@router.get("")
def get_logs(server_id: int, limit: int = Query(200, ge=1, le=2000)):
    """Read JSON log lines from backend/log/{server_id}.log"""
    path = os.path.join(LOG_DIR, f"{server_id}.log")
    if not os.path.exists(path):
        return {"total": 0, "logs": []}

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    total = len(lines)
    # Return most recent `limit` lines
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


@router.delete("/clear", status_code=204)
def clear_logs(server_id: int):
    """Clear the server's log file."""
    path = os.path.join(LOG_DIR, f"{server_id}.log")
    if os.path.exists(path):
        open(path, "w").close()