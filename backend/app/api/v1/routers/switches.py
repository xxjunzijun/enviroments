import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.switch import Switch
from app.models.server import Server
from app.api.v1.schemas import (
    SwitchCreate, SwitchUpdate, SwitchResponse,
    SwitchListResponse, ServerSwitchAssocRequest
)

router = APIRouter(prefix="/switches", tags=["switches"])


@router.get("", response_model=SwitchListResponse)
def list_switches(db: Session = Depends(get_db)):
    switches = db.query(Switch).order_by(Switch.name).all()
    return SwitchListResponse(
        total=len(switches),
        switches=[_to_response(s) for s in switches]
    )


@router.get("/{switch_id}", response_model=SwitchResponse)
def get_switch(switch_id: int, db: Session = Depends(get_db)):
    switch = db.query(Switch).filter(Switch.id == switch_id).first()
    if not switch:
        raise HTTPException(status_code=404, detail="Switch not found")
    return _to_response(switch)


@router.post("", response_model=SwitchResponse, status_code=201)
def create_switch(data: SwitchCreate, db: Session = Depends(get_db)):
    existing = db.query(Switch).filter(Switch.ip == data.ip).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"IP {data.ip} already registered")

    switch = Switch(
        name=data.name,
        ip=data.ip,
        port=data.port,
        username=data.username,
        password=data.password,
        description=data.description,
        tags=data.tags,
    )
    db.add(switch)
    db.commit()
    db.refresh(switch)
    return _to_response(switch)


@router.put("/{switch_id}", response_model=SwitchResponse)
def update_switch(switch_id: int, data: SwitchUpdate, db: Session = Depends(get_db)):
    switch = db.query(Switch).filter(Switch.id == switch_id).first()
    if not switch:
        raise HTTPException(status_code=404, detail="Switch not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(switch, field, value)

    db.commit()
    db.refresh(switch)
    return _to_response(switch)


@router.delete("/{switch_id}", status_code=204)
def delete_switch(switch_id: int, db: Session = Depends(get_db)):
    switch = db.query(Switch).filter(Switch.id == switch_id).first()
    if not switch:
        raise HTTPException(status_code=404, detail="Switch not found")
    db.delete(switch)
    db.commit()


@router.get("/{switch_id}/servers")
def get_switch_servers(switch_id: int, db: Session = Depends(get_db)):
    """获取关联到此交换机的所有服务器 ID 列表"""
    switch = db.query(Switch).filter(Switch.id == switch_id).first()
    if not switch:
        raise HTTPException(status_code=404, detail="Switch not found")
    return [s.id for s in switch.servers]


@router.post("/server/{server_id}/switches", status_code=204)
def set_server_switches(server_id: int, data: ServerSwitchAssocRequest, db: Session = Depends(get_db)):
    """设置服务器关联的交换机列表"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    switches = db.query(Switch).filter(Switch.id.in_(data.switch_ids)).all()
    server.switches = switches
    db.commit()


@router.get("/server/{server_id}/switches", response_model=SwitchListResponse)
def get_server_switches(server_id: int, db: Session = Depends(get_db)):
    """获取服务器关联的所有交换机"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return SwitchListResponse(
        total=len(server.switches),
        switches=[_to_response(s) for s in server.switches]
    )


def _to_response(switch: Switch) -> SwitchResponse:
    return SwitchResponse(
        id=switch.id,
        name=switch.name,
        ip=switch.ip,
        port=switch.port,
        username=switch.username,
        password=switch.password,
        description=switch.description,
        tags=switch.tags,
        created_at=switch.created_at,
        updated_at=switch.updated_at,
    )
