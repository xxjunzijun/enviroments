from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ServerBase(BaseModel):
    hostname: str
    ip: str
    port: int = 22
    os_type: str = "linux"
    ssh_username: str
    ssh_password: Optional[str] = None
    ssh_key_file: Optional[str] = None
    description: Optional[str] = None
    tags: str = ""


class ServerCreate(ServerBase):
    pass


class ServerUpdate(BaseModel):
    hostname: Optional[str] = None
    port: Optional[int] = None
    os_type: Optional[str] = None
    ssh_username: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_key_file: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None


class ServerResponse(ServerBase):
    id: int
    is_online: bool
    online_checked_at: Optional[datetime] = None
    cached_hostname: Optional[str] = None
    cached_os_version: Optional[str] = None
    cached_cpu_count: Optional[int] = None
    cached_memory_total: Optional[int] = None
    cached_interfaces: Optional[list] = None
    cached_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ServerListResponse(BaseModel):
    total: int
    servers: list[ServerResponse]


class StatusCheckResponse(BaseModel):
    ip: str
    online: bool
    ssh_open: bool
    message: Optional[str] = None


class ServerDetailResponse(BaseModel):
    id: int
    hostname: str
    ip: str
    os_type: str
    os_version: Optional[str] = None
    cpu_count: Optional[int] = None
    memory_total: Optional[int] = None
    interfaces: Optional[list] = None
    is_online: bool
    description: Optional[str] = None
    tags: str
    cached_at: Optional[datetime] = None
