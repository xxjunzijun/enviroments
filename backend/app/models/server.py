from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from datetime import datetime
from app.core.database import Base


class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String(255), nullable=False)
    ip = Column(String(45), unique=True, nullable=False)  # IPv4/IPv6
    port = Column(Integer, default=22)
    os_type = Column(String(50), default="linux")  # linux | windows
    ssh_username = Column(String(255), nullable=False)
    ssh_password = Column(String(255), nullable=True)  # nullable for key auth
    ssh_key_file = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    tags = Column(String(500), default="")  # comma-separated

    # Cached info
    cached_hostname = Column(String(255), nullable=True)
    cached_os_version = Column(String(255), nullable=True)
    cached_cpu_count = Column(Integer, nullable=True)
    cached_memory_total = Column(Integer, nullable=True)
    cached_interfaces = Column(Text, nullable=True)  # JSON string
    cached_at = Column(DateTime, nullable=True)

    is_online = Column(Boolean, default=False)
    online_checked_at = Column(DateTime, nullable=True)
    status_check_interval = Column(Integer, default=5)   # minutes
    detail_fetch_interval = Column(Integer, default=30)  # minutes

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ServerLog(Base):
    """Log of server status and detail changes over time."""
    __tablename__ = "server_logs"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # "status_check" | "detail_fetch"
    is_online = Column(Boolean, nullable=True)
    os_version = Column(String(255), nullable=True)
    cpu_count = Column(Integer, nullable=True)
    memory_total = Column(Integer, nullable=True)
    interfaces_json = Column(Text, nullable=True)  # JSON string
    error_message = Column(Text, nullable=True)
    logged_at = Column(DateTime, default=datetime.utcnow)