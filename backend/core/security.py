from typing import Optional

from fastapi import Request

from core.config import settings
from core.errors import AppError


def get_auth_token(request: Request) -> Optional[str]:
    return request.cookies.get(settings.auth_cookie)


def ensure_admin(*, is_admin: bool) -> None:
    if not is_admin:
        raise AppError("forbidden", "无权限", status_code=403)


def normalize_owner_role(owner_role: Optional[str]) -> Optional[str]:
    if owner_role is None:
        return None
    role = owner_role.strip().lower()
    if role not in {"admin", "user"}:
        raise AppError("invalid_owner_role", "owner_role must be admin or user", status_code=400)
    return role
