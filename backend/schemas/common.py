from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PaginationQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=50, ge=1, le=500)


class TimeRangeQuery(BaseModel):
    date_from: Optional[str] = None
    date_to: Optional[str] = None


class IdListPayload(BaseModel):
    ids: list[int] = []


class ApiError(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None
    timestamp: Optional[datetime] = None
