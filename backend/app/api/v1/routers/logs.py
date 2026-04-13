from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.server import Server, ServerLog
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/servers/{server_id}/logs", tags=["logs"])


class LogEntry(BaseModel):
    id: int
    server_id: int
    event_type: str
    is_online: Optional[bool]
    os_version: Optional[str]
    cpu_count: Optional[int]
    memory_total: Optional[int]
    interfaces_json: Optional[str]
    error_message: Optional[str]
    logged_at: datetime


class LogListResponse(BaseModel):
    total: int
    logs: list[LogEntry]


@router.get("", response_model=LogListResponse)
def get_logs(
    server_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = SessionLocal()
    try:
        server = db.query(Server).filter(Server.id == server_id).first()
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")

        total = db.query(ServerLog).filter(ServerLog.server_id == server_id).count()
        logs = (
            db.query(ServerLog)
            .filter(ServerLog.server_id == server_id)
            .order_by(ServerLog.logged_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return LogListResponse(total=total, logs=logs)
    finally:
        db.close()


@router.delete("/clear", status_code=204)
def clear_logs(server_id: int):
    db = SessionLocal()
    try:
        server = db.query(Server).filter(Server.id == server_id).first()
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
        db.query(ServerLog).filter(ServerLog.server_id == server_id).delete()
        db.commit()
    finally:
        db.close()