from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.db import Base


class BrowseLog(Base):
    __tablename__ = "browse_logs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    username = Column(String(100), nullable=False, index=True)
    role = Column(String(20), nullable=False, index=True)
    event_type = Column(String(20), nullable=False, index=True)  # page_view / action
    path = Column(String(300), nullable=False, index=True)
    module = Column(String(100), nullable=True, index=True)
    ip = Column(String(100), nullable=True)
    user_agent = Column(String(300), nullable=True)
    detail = Column(Text, nullable=True)
