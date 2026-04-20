from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.db import Base


class MonitorSite(Base):
    __tablename__ = "monitor_sites"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    name = Column(String(150), nullable=False, index=True)
    url = Column(String(500), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    interval_sec = Column(Integer, default=60, nullable=False)
    timeout_sec = Column(Integer, default=8, nullable=False)
    last_checked_at = Column(DateTime, nullable=True)
    last_status_code = Column(Integer, nullable=True)
    last_response_ms = Column(Integer, nullable=True)
    last_ok = Column(Boolean, nullable=True)
    last_error = Column(Text, nullable=True)


class MonitorSiteResult(Base):
    __tablename__ = "monitor_site_results"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    site_id = Column(Integer, ForeignKey("monitor_sites.id"), nullable=False, index=True)
    status_code = Column(Integer, nullable=True)
    response_ms = Column(Integer, nullable=True)
    ok = Column(Boolean, nullable=False, default=False, index=True)
    error = Column(Text, nullable=True)

    site = relationship("MonitorSite")
