"""
Background scheduler for periodic server status and detail checks.
Writes JSON-line logs to backend/log/{server_id}.log
"""

import os
import json
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.database import SessionLocal
from app.models.server import Server
from infrastructure.ssh_client import check_online, get_server_info_via_ssh

logger = logging.getLogger("scheduler")

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "log")


def _log_line(server_id: int, payload: dict):
    """Append a JSON line to the server's log file."""
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, f"{server_id}.log")
    payload["time"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    line = json.dumps(payload, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _read_logs(server_id: int, limit: int = 200) -> list[dict]:
    """Read last `limit` JSON log lines for a server."""
    path = os.path.join(LOG_DIR, f"{server_id}.log")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    result = []
    for raw in reversed(lines[-limit:]):
        raw = raw.strip()
        if raw:
            try:
                result.append(json.loads(raw))
            except Exception:
                pass
    return result


async def status_check_task(app):
    """Ping all servers, update online status, write JSON log lines."""
    db = SessionLocal()
    try:
        servers = db.query(Server).all()
        now = datetime.utcnow()
        for server in servers:
            # Rate limit: skip if checked recently per interval
            if server.online_checked_at:
                elapsed = (now - server.online_checked_at).total_seconds() / 60
                if elapsed < (server.status_check_interval or 5):
                    continue

            online = check_online(server.ip, port=server.port)
            was_online = server.is_online
            server.is_online = online
            server.online_checked_at = now

            _log_line(server.id, {
                "type": "status_check",
                "online": online,
                "changed": was_online != online,
            })

        db.commit()
        logger.info(f"[Scheduler] Status check done for {len(servers)} servers")
    except Exception as e:
        logger.error(f"[Scheduler] Status check error: {e}")
        db.rollback()
    finally:
        db.close()


async def detail_fetch_task(app):
    """SSH fetch full server info, cache and write JSON log lines."""
    db = SessionLocal()
    try:
        servers = db.query(Server).all()
        now = datetime.utcnow()
        for server in servers:
            # Rate limit: skip if fetched recently per interval
            if server.cached_at:
                elapsed = (now - server.cached_at).total_seconds() / 60
                if elapsed < (server.detail_fetch_interval or 30):
                    continue

            info = get_server_info_via_ssh(
                ip=server.ip,
                username=server.ssh_username,
                password=server.ssh_password,
                key_file=server.ssh_key_file,
                port=server.port,
            )

            if info.error:
                _log_line(server.id, {
                    "type": "detail_fetch",
                    "online": server.is_online,
                    "error": info.error,
                })
            else:
                snapshot = {
                    "type": "detail_fetch",
                    "online": server.is_online,
                    "os_type": info.os_type,
                    "os_version": info.os_version,
                    "cpu": info.cpu_count,
                    "mem": info.memory_total,
                    "interfaces": info.interfaces or [],
                    "hostname": info.hostname,
                }
                _log_line(server.id, snapshot)

                # Update cached snapshot in DB
                server.cached_info = json.dumps(snapshot, ensure_ascii=False)
                server.cached_at = now
                server.is_online = True  # SSH worked = online

        db.commit()
        logger.info(f"[Scheduler] Detail fetch done for {len(servers)} servers")
    except Exception as e:
        logger.error(f"[Scheduler] Detail fetch error: {e}")
        db.rollback()
    finally:
        db.close()


def create_scheduler(app) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        status_check_task,
        trigger=IntervalTrigger(minutes=5),
        args=[app],
        id="status_check",
        name="Server Status Check (every 5 min)",
        replace_existing=True,
    )

    scheduler.add_job(
        detail_fetch_task,
        trigger=IntervalTrigger(minutes=30),
        args=[app],
        id="detail_fetch",
        name="Server Detail Fetch (every 30 min)",
        replace_existing=True,
    )

    return scheduler