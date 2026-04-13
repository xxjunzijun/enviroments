import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.server import Server
from app.api.v1.schemas import (
    ServerCreate, ServerUpdate, ServerResponse,
    ServerListResponse, StatusCheckResponse, ServerDetailResponse
)
from infrastructure.ssh_client import get_server_info_via_ssh, check_online, ServerInfo

router = APIRouter(prefix="/servers", tags=["servers"])


@router.get("", response_model=ServerListResponse)
def list_servers(db: Session = Depends(get_db)):
    servers = db.query(Server).order_by(Server.ip).all()
    return ServerListResponse(
        total=len(servers),
        servers=[_to_response(s) for s in servers]
    )


@router.get("/{server_id}", response_model=ServerResponse)
def get_server(server_id: int, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return _to_response(server)


@router.post("", response_model=ServerResponse, status_code=201)
def create_server(data: ServerCreate, db: Session = Depends(get_db)):
    existing = db.query(Server).filter(Server.ip == data.ip).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"IP {data.ip} already registered")

    server = Server(
        ip=data.ip,
        port=data.port,
        os_type=data.os_type,
        ssh_username=data.ssh_username,
        ssh_password=data.ssh_password,
        ssh_key_file=data.ssh_key_file,
        description=data.description,
        tags=data.tags,
    )
    db.add(server)
    db.commit()
    db.refresh(server)
    return _to_response(server)


@router.put("/{server_id}", response_model=ServerResponse)
def update_server(server_id: int, data: ServerUpdate, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(server, field, value)

    db.commit()
    db.refresh(server)
    return _to_response(server)


@router.delete("/{server_id}", status_code=204)
def delete_server(server_id: int, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    db.delete(server)
    db.commit()


@router.get("/{server_id}/status", response_model=StatusCheckResponse)
def check_status(server_id: int, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    online = check_online(server.ip, port=server.port)
    server.is_online = online
    server.online_checked_at = datetime.utcnow()
    db.commit()

    return StatusCheckResponse(
        ip=server.ip,
        online=online,
        ssh_open=online,
        message=None if online else "Server is unreachable"
    )


@router.get("/{server_id}/detail", response_model=ServerDetailResponse)
def fetch_detail(server_id: int, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    info: ServerInfo = get_server_info_via_ssh(
        ip=server.ip,
        username=server.ssh_username,
        password=server.ssh_password,
        key_file=server.ssh_key_file,
        port=server.port,
    )

    now = datetime.utcnow()
    if info.error:
        raise HTTPException(status_code=502, detail=f"SSH error: {info.error}")

    snapshot = {
        "os_type": info.os_type,
        "os_version": info.os_version,
        "cpu": info.cpu_count,
        "mem": info.memory_total,
        "interfaces": info.interfaces or [],
        "hostname": info.hostname,
    }
    server.cached_info = json.dumps(snapshot, ensure_ascii=False)
    server.cached_at = now
    server.is_online = True
    db.commit()

    return ServerDetailResponse(
        id=server.id,
        ip=server.ip,
        os_type=info.os_type,
        os_version=info.os_version,
        cpu=info.cpu_count,
        mem=info.memory_total,
        interfaces=info.interfaces or [],
        is_online=True,
        description=server.description,
        tags=server.tags,
        cached_at=server.cached_at,
    )


def _to_response(server: Server) -> ServerResponse:
    cached_info = None
    if server.cached_info:
        try:
            cached_info = json.loads(server.cached_info)
        except Exception:
            pass

    return ServerResponse(
        id=server.id,
        ip=server.ip,
        port=server.port,
        os_type=server.os_type,
        ssh_username=server.ssh_username,
        ssh_password=server.ssh_password,
        ssh_key_file=server.ssh_key_file,
        description=server.description,
        tags=server.tags,
        is_online=server.is_online,
        online_checked_at=server.online_checked_at,
        cached_info=cached_info,
        cached_at=server.cached_at,
        created_at=server.created_at,
        updated_at=server.updated_at,
    )