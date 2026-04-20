from typing import Optional

from sqlalchemy.orm import Query

from core.errors import AppError

VALID_OWNER_ROLES = {"admin", "user"}


def is_admin_role(role: str) -> bool:
    return str(role or "").strip().lower() == "admin"


def owner_role_for_create(role: str) -> str:
    return "admin" if is_admin_role(role) else "user"


def normalize_scope_owner_role(role: str, owner_role: Optional[str] = None) -> Optional[str]:
    if owner_role is None:
        return None
    normalized = str(owner_role).strip().lower()
    if normalized not in VALID_OWNER_ROLES:
        raise AppError("invalid_owner_role", "owner_role must be admin or user", status_code=400)
    if not is_admin_role(role) and normalized != "user":
        raise AppError("forbidden", "无权限", status_code=403)
    return normalized


def apply_owner_scope(query: Query, model, role: str, owner_role: Optional[str] = None) -> Query:
    target_role = normalize_scope_owner_role(role, owner_role)
    if is_admin_role(role):
        if target_role:
            return query.filter(model.owner_role == target_role)
        return query
    return query.filter(model.owner_role == "user")


def ensure_row_visible(owner_role: str, role: str) -> None:
    if is_admin_role(role):
        return
    if owner_role != "user":
        raise AppError("not_found", "记录不存在", status_code=404)
