from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from app.core.database import Base


class ServerFavorite(Base):
    __tablename__ = "server_favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "server_id", name="uq_server_favorite_user_server"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False, index=True)
