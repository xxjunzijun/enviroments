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

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
