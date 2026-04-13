"""
Background scheduler for periodic server status and detail checks.
Runs as an independent asyncio task inside the FastAPI app lifecycle.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.server import Server, ServerLog
from infrastructure.ssh_client import check_online, get_server_info_via_ssh, ServerInfo

logger = logging.getLogger("scheduler")


def save_log(db: Session, server_id: int, event_type: str, info: ServerInfo = None, error: str = None):
    """Save a server event to the server_logs table."""
    log = ServerLog(
        server_id=server_id,
        event_type=event_type,
        is_online=info.is_online if info else None,
        os_version=info.os_version if info else None,
        cpu_count=info.cpu_count if info else None,
        memory_total=info.memory_total if info else None,
        interfaces_json=json.dumps(info.interfaces) if info and info.interfaces else None,
        error_message=error,
    )
    db.add(log)


async def check_all_servers_status():
    """Ping all servers to update online/offline status."""
    db = SessionLocal()
    try:
        servers = db.query(Server).all()
        now = datetime.utcnow()
        for server in servers:
            online = check_online(server.ip, port=server.port)
            was_online = server.is_online
            server.is_online = online
            server.online_checked_at = now

            # Log state change
            if was_online != online:
                save_log(db, server.id, "status_check", error=f"State changed: {'online' if online else 'offline'}" if not online else None)

        db.commit()
        logger.info(f"[Scheduler] Status check done for {len(servers)} servers")
    except Exception as e:
        logger.error(f"[Scheduler] Status check error: {e}")
        db.rollback()
    finally:
        db.close()


async def check_server_status(server: Server, db: Session):
    """Ping one server and update its online status."""
    try:
        online = check_online(server.ip, port=server.port)
        was_online = server.is_online
        server.is_online = online
        server.online_checked_at = datetime.utcnow()

        if was_online != online:
            save_log(db, server.id, "status_check",
                     error=None if online else "Became unreachable")

        return online
    except Exception as e:
        save_log(db, server.id, "status_check", error=str(e))
        return False


async def fetch_server_detail(server: Server, db: Session):
    """SSH fetch full server info and log the result."""
    try:
        info = get_server_info_via_ssh(
            ip=server.ip,
            username=server.ssh_username,
            password=server.ssh_password,
            key_file=server.ssh_key_file,
            port=server.port,
        )
        if info.error:
            save_log(db, server.id, "detail_fetch", error=info.error)
        else:
            server.cached_hostname = info.hostname
            server.cached_os_version = info.os_version
            server.cached_cpu_count = info.cpu_count
            server.cached_memory_total = info.memory_total
            server.cached_interfaces = json.dumps(info.interfaces or [])
            server.cached_at = datetime.utcnow()
            server.hostname = info.hostname
            save_log(db, server.id, "detail_fetch", info=info)

        return info
    except Exception as e:
        save_log(db, server.id, "detail_fetch", error=str(e))
        return None


async def status_check_task(app):
    """Interval task: check online status for all servers."""
    db = SessionLocal()
    try:
        servers = db.query(Server).all()
        now = datetime.utcnow()
        for server in servers:
            # Only check if interval has passed since last check
            if server.online_checked_at:
                elapsed = (now - server.online_checked_at).total_seconds() / 60
                if elapsed < server.status_check_interval:
                    continue

            online = check_online(server.ip, port=server.port)
            was_online = server.is_online
            server.is_online = online
            server.online_checked_at = now

            if was_online != online:
                save_log(db, server.id, "status_check",
                         error=None if online else "Became unreachable")
        db.commit()
        logger.info(f"[Scheduler] Status check done for {len(servers)} servers")
    except Exception as e:
        logger.error(f"[Scheduler] Status check error: {e}")
        db.rollback()
    finally:
        db.close()


async def detail_fetch_task(app):
    """Interval task: SSH fetch details for all servers."""
    db = SessionLocal()
    try:
        servers = db.query(Server).all()
        now = datetime.utcnow()
        for server in servers:
            # Only fetch if interval has passed since last fetch
            if server.cached_at:
                elapsed = (now - server.cached_at).total_seconds() / 60
                if elapsed < server.detail_fetch_interval:
                    continue

            info = get_server_info_via_ssh(
                ip=server.ip,
                username=server.ssh_username,
                password=server.ssh_password,
                key_file=server.ssh_key_file,
                port=server.port,
            )
            if info.error:
                save_log(db, server.id, "detail_fetch", error=info.error)
            else:
                server.cached_hostname = info.hostname
                server.cached_os_version = info.os_version
                server.cached_cpu_count = info.cpu_count
                server.cached_memory_total = info.memory_total
                server.cached_interfaces = json.dumps(info.interfaces or [])
                server.cached_at = now
                server.hostname = info.hostname
                save_log(db, server.id, "detail_fetch", info=info)

        db.commit()
        logger.info(f"[Scheduler] Detail fetch done for {len(servers)} servers")
    except Exception as e:
        logger.error(f"[Scheduler] Detail fetch error: {e}")
        db.rollback()
    finally:
        db.close()


def create_scheduler(app) -> AsyncIOScheduler:
    """Create and configure the background scheduler."""
    scheduler = AsyncIOScheduler()

    # Status check every 5 minutes
    scheduler.add_job(
        status_check_task,
        trigger=IntervalTrigger(minutes=5),
        args=[app],
        id="status_check",
        name="Server Status Check (every 5 min)",
        replace_existing=True,
    )

    # Detail fetch every 30 minutes
    scheduler.add_job(
        detail_fetch_task,
        trigger=IntervalTrigger(minutes=30),
        args=[app],
        id="detail_fetch",
        name="Server Detail Fetch (every 30 min)",
        replace_existing=True,
    )

    return scheduler