from typing import Optional

from pydantic import BaseModel


class MonitorSiteCreateBody(BaseModel):
    name: str
    url: str
    enabled: Optional[bool] = True
    interval_sec: Optional[int] = 60
    timeout_sec: Optional[int] = 8


class MonitorSiteUpdateBody(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    enabled: Optional[bool] = None
    interval_sec: Optional[int] = None
    timeout_sec: Optional[int] = None
