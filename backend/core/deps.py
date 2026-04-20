from typing import Optional

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from core import context
from core.db import get_db
from core.security import ensure_admin, normalize_owner_role


def db_session(db: Session = Depends(get_db)) -> Session:
    return db


def get_current_username(request: Request) -> str:
    return getattr(request.state, "username", context.username())


def get_current_role(request: Request) -> str:
    return getattr(request.state, "role", context.role())


def require_admin(request: Request) -> None:
    ensure_admin(is_admin=bool(getattr(request.state, "is_admin", context.is_admin())))


def owner_role_filter_param(owner_role: Optional[str] = Query(None)) -> Optional[str]:
    return normalize_owner_role(owner_role)


def parse_page(page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=500)) -> tuple[int, int]:
    return page, size
