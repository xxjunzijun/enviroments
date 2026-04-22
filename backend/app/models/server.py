from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Server(Base):
    __tablename__ = "servers"

    switches = relationship(
        "Switch",
        secondary="server_switches",
        back_populates="servers",
        lazy="selectin"
    )

    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String(45), unique=True, nullable=False)
    port = Column(Integer, default=22)
    os_type = Column(String(50), default="linux")
    ssh_username = Column(String(255), nullable=False)
    ssh_password = Column(String(255), nullable=True)
    ssh_key_file = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    detail_note = Column(Text, nullable=True)
    tags = Column(String(500), default="")
    bmc_ip = Column(String(45), nullable=True)
    bmc_username = Column(String(255), nullable=True)
    bmc_password = Column(String(255), nullable=True)
    occupied_by = Column(String(50), nullable=True)     # 当前占用者用户名
    occupied_at = Column(DateTime, nullable=True)

    cached_info = Column(Text, nullable=True)          # JSON: latest full info snapshot
    cached_at = Column(DateTime, nullable=True)

    is_online = Column(Boolean, default=False)
    online_checked_at = Column(DateTime, nullable=True)
    status_check_interval = Column(Integer, default=5)   # minutes
    detail_fetch_interval = Column(Integer, default=30)  # minutes

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
