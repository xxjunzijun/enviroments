import json
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.server import Server
from app.models.server_favorite import ServerFavorite
from app.api.v1.schemas import (
    ServerCreate, ServerUpdate, ServerResponse,
    ServerListResponse, StatusCheckResponse, ServerDetailResponse
)
from infrastructure.ssh_client import get_server_info_via_ssh, check_online, ServerInfo

router = APIRouter(prefix="/servers", tags=["servers"], dependencies=[Depends(get_current_user)])

from app.core.scheduler import LOG_DIR as _LOG_DIR


def _write_log(server_id: int, payload: dict):
    os.makedirs(_LOG_DIR, exist_ok=True)
    payload = dict(payload)
    payload["time"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    line = json.dumps(payload, ensure_ascii=False)
    with open(os.path.join(_LOG_DIR, f"{server_id}.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _update_server_fields(db: Session, server_id: int, values: dict) -> bool:
    updated = db.query(Server).filter(Server.id == server_id).update(
        values,
        synchronize_session=False,
    )
    db.commit()
    return updated == 1


@router.get("", response_model=ServerListResponse)
def list_servers(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    servers = db.query(Server).order_by(Server.ip).all()
    favorite_ids = _favorite_server_ids(db, current_user.id)
    return ServerListResponse(
        total=len(servers),
        servers=[_to_response(s, s.id in favorite_ids) for s in servers]
    )


@router.post("/{server_id}/occupy", response_model=ServerResponse)
def occupy_server(server_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """占用服务器；如果已被他人占用，则由当前用户强制接管。"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    server.occupied_by = current_user.username
    db.commit()
    db.refresh(server)
    return _to_response(server)


@router.post("/{server_id}/release", response_model=ServerResponse)
def release_server(server_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """閲婃斁鏈嶅姟鍣紙鍙湁鏈汉鎴栫鐞嗗憳鍙噴鏀撅級"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    if server.occupied_by and server.occupied_by != current_user.username:
        raise HTTPException(status_code=403, detail="鍙兘鏈汉鎴栫鐞嗗憳閲婃斁")
    server.occupied_by = None
    db.commit()
    db.refresh(server)
    return _to_response(server)


@router.get("/{server_id}", response_model=ServerResponse)
def get_server(server_id: int, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return _to_response(server)


@router.post("/{server_id}/favorite", response_model=ServerResponse)
def favorite_server(server_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    existing = db.query(ServerFavorite).filter(
        ServerFavorite.user_id == current_user.id,
        ServerFavorite.server_id == server_id,
    ).first()
    if not existing:
        db.add(ServerFavorite(user_id=current_user.id, server_id=server_id))
        db.commit()

    return _to_response(server, is_favorite=True)


@router.delete("/{server_id}/favorite", response_model=ServerResponse)
def unfavorite_server(server_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    favorite = db.query(ServerFavorite).filter(
        ServerFavorite.user_id == current_user.id,
        ServerFavorite.server_id == server_id,
    ).first()
    if favorite:
        db.delete(favorite)
        db.commit()

    return _to_response(server, is_favorite=False)


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
        detail_note=data.detail_note,
        tags=data.tags,
        bmc_ip=data.bmc_ip,
        bmc_username=data.bmc_username,
        bmc_password=data.bmc_password,
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
    db.query(ServerFavorite).filter(ServerFavorite.server_id == server_id).delete()
    db.delete(server)
    db.commit()


@router.get("/{server_id}/status", response_model=StatusCheckResponse)
def check_status(server_id: int, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    online = check_online(server.ip, port=server.port)
    was_online = server.is_online
    if not _update_server_fields(db, server_id, {
        "is_online": online,
        "online_checked_at": datetime.utcnow(),
    }):
        raise HTTPException(status_code=404, detail="Server not found")

    _write_log(server_id, {
        "type": "status_check",
        "online": online,
        "changed": was_online != online,
    })

    return StatusCheckResponse(
        ip=server.ip,
        online=online,
        ssh_open=online,
        message=None if online else "Server is unreachable"
    )


@router.get("/{server_id}/detail", response_model=ServerDetailResponse)
def fetch_detail(server_id: int, refresh: bool = False, db: Session = Depends(get_db)):
    """
    鑾峰彇鏈嶅姟鍣ㄨ鎯呫€?
    - refresh=false锛堥粯璁わ級锛氫紭鍏堜粠 cached_info 杩斿洖锛屾绉掔骇鍝嶅簲
    - refresh=true锛氬己鍒?SSH 閲嶆柊閲囬泦锛?閲嶆柊閲囬泦"鎸夐挳浣跨敤锛?
    """
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    # 涓嶅己鍒跺埛鏂版椂锛屼紭鍏堣繑鍥炵紦瀛?
    if not refresh and server.cached_info:
        try:
            cached = json.loads(server.cached_info)
            return ServerDetailResponse(
                id=server_id,
                ip=server.ip,
                os_type=cached.get("os_type", server.os_type),
                os_version=cached.get("os_version"),
                cpu_model=cached.get("cpu_model"),
                cpu=cached.get("cpu"),
                mem=cached.get("mem"),
                interfaces=cached.get("interfaces") or [],
                is_online=server.is_online,
                description=server.description,
                detail_note=server.detail_note,
                tags=server.tags,
                cached_at=server.cached_at,
            )
        except Exception:
            pass  # 缂撳瓨鎹熷潖锛岄檷绾у埌 SSH 閲囬泦

    # SSH 閲嶆柊閲囬泦
    detail_context = {
        "ip": server.ip,
        "username": server.ssh_username,
        "password": server.ssh_password,
        "key_file": server.ssh_key_file,
        "port": server.port,
        "description": server.description,
        "detail_note": server.detail_note,
        "tags": server.tags,
    }

    info: ServerInfo = get_server_info_via_ssh(
        ip=detail_context["ip"],
        username=detail_context["username"],
        password=detail_context["password"],
        key_file=detail_context["key_file"],
        port=detail_context["port"],
    )

    now = datetime.utcnow()
    if info.error:
        _write_log(server.id, {
            "type": "detail_fetch",
            "online": False,
            "error": info.error,
        })
        raise HTTPException(status_code=502, detail=f"SSH error: {info.error}")

    snapshot = {
        "type": "detail_fetch",
        "online": True,
        "os_type": info.os_type,
        "os_version": info.os_version,
        "cpu_model": info.cpu_model,
        "cpu": info.cpu_count,
        "mem": info.memory_total,
        "interfaces": info.interfaces or [],
        "hostname": info.hostname,
    }
    _write_log(server.id, snapshot)

    if not _update_server_fields(db, server.id, {
        "cached_info": json.dumps(snapshot, ensure_ascii=False),
        "cached_at": now,
        "is_online": True,
    }):
        raise HTTPException(status_code=404, detail="Server not found")

    return ServerDetailResponse(
        id=server_id,
        ip=detail_context["ip"],
        os_type=info.os_type,
        os_version=info.os_version,
        cpu_model=info.cpu_model,
        cpu=info.cpu_count,
        mem=info.memory_total,
        interfaces=info.interfaces or [],
        is_online=True,
        description=detail_context["description"],
        detail_note=detail_context["detail_note"],
        tags=detail_context["tags"],
        cached_at=now,
    )


def _favorite_server_ids(db: Session, user_id: int) -> set[int]:
    rows = db.query(ServerFavorite.server_id).filter(ServerFavorite.user_id == user_id).all()
    return {server_id for (server_id,) in rows}


def _to_response(server: Server, is_favorite: bool = False) -> ServerResponse:
    cached_info = None
    cached_os_version = None
    cached_cpu_model = None
    cached_hostname = None
    cached_mem = None
    cached_interfaces = None
    if server.cached_info:
        try:
            cached_info = json.loads(server.cached_info)
            cached_os_version = cached_info.get("os_version") if cached_info else None
            cached_cpu_model = cached_info.get("cpu_model") if cached_info else None
            cached_hostname = cached_info.get("hostname") if cached_info else None
            cached_mem = cached_info.get("mem") if cached_info else None
            cached_interfaces = cached_info.get("interfaces") if cached_info else None
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
        detail_note=server.detail_note,
        tags=server.tags,
        bmc_ip=server.bmc_ip,
        bmc_username=server.bmc_username,
        bmc_password=server.bmc_password,
        is_online=server.is_online,
        online_checked_at=server.online_checked_at,
        cached_info=cached_info,
        cached_at=server.cached_at,
        created_at=server.created_at,
        updated_at=server.updated_at,
        cached_os_version=cached_os_version,
        cached_cpu_model=cached_cpu_model,
        cached_hostname=cached_hostname,
        cached_mem=cached_mem,
        cached_interfaces=cached_interfaces,
        occupied_by=server.occupied_by,
        assoc_switch_count=len(server.switches) if server.switches else 0,
        is_favorite=is_favorite,
    )
