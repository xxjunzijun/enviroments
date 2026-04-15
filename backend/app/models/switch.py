from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Table
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

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联的服务器通过 association table 访问
    servers = relationship(
        "Server",
        secondary="server_switches",
        back_populates="switches",
        lazy="selectin"
    )


# 关联表：服务器 ↔ 交换机（多对多）
server_switches = Table(
    "server_switches",
    Base.metadata,
    Column("server_id", Integer, ForeignKey("servers.id", ondelete="CASCADE"), primary_key=True),
    Column("switch_id", Integer, ForeignKey("switches.id", ondelete="CASCADE"), primary_key=True),
)
