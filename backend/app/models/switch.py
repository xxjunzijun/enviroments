from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Table, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Switch(Base):
    __tablename__ = "switches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    ip = Column(String(45), unique=True, nullable=False)
    port = Column(Integer, default=22)
    username = Column(String(255), nullable=False)
    password = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    tags = Column(String(500), default="")

    cached_info = Column(Text, nullable=True)          # JSON: latest full info snapshot
    cached_at = Column(DateTime, nullable=True)
    is_online = Column(Boolean, default=False)
    online_checked_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    servers = relationship(
        "Server",
        secondary="server_switches",
        back_populates="switches",
        lazy="selectin"
    )


server_switches = Table(
    "server_switches",
    Base.metadata,
    Column("server_id", Integer, ForeignKey("servers.id", ondelete="CASCADE"), primary_key=True),
    Column("switch_id", Integer, ForeignKey("switches.id", ondelete="CASCADE"), primary_key=True),
)
