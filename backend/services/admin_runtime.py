from __future__ import annotations

import json
from typing import Dict, List, Optional

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import hash_password
from core import context
from core.db import get_db
from core.security import ensure_admin
from models import User
from services.audit_runtime import write_browse_log
from services.auth_runtime import (
    default_data_permissions,
    default_module_permissions,
    normalize_data_permissions,
    normalize_module_permissions,
    serialize_user_permissions,
)


def _current_username() -> str:
    return context.username()


def _current_role() -> str:
    return context.role()


def _require_admin() -> None:
    ensure_admin(is_admin=context.is_admin())


class UserCreateBody(BaseModel):
    username: str
    password: str


class UserResetPasswordBody(BaseModel):
    password: str


class UserUpdateBody(BaseModel):
    role: Optional[str] = None
    password: Optional[str] = None
    module_permissions: Optional[List[str]] = None
    data_permissions: Optional[Dict[str, str]] = None


def admin_list_users(db: Session = Depends(get_db)):
    _require_admin()
    rows = db.query(User).order_by(User.created_at.desc(), User.id.desc()).all()
    out = []
    for x in rows:
        module_permissions, data_permissions = serialize_user_permissions(x)
        if (x.role or "user").strip().lower() == "admin":
            module_permissions = default_module_permissions()
            data_permissions = default_data_permissions()
        out.append(
            {
                "id": x.id,
                "username": x.username,
                "role": x.role,
                "is_active": bool(x.is_active),
                "module_permissions": module_permissions,
                "data_permissions": data_permissions,
                "created_at": x.created_at,
                "updated_at": x.updated_at,
            }
        )
    return out


def admin_create_user(body: UserCreateBody, request: Request, db: Session = Depends(get_db)):
    _require_admin()
    username = (body.username or "").strip()
    password = str(body.password or "")
    if not username:
        raise HTTPException(400, "username 不能为空")
    if username.lower() == "xiaoyao":
        raise HTTPException(400, "xiaoyao 为保留管理员账号")
    if len(password) < 4:
        raise HTTPException(400, "password 至少 4 位")
    existed = db.query(User).filter(User.username == username).first()
    if existed:
        raise HTTPException(400, "用户名已存在")
    obj = User(
        username=username,
        password_hash=hash_password(password),
        role="user",
        is_active=True,
        module_permissions=json.dumps(default_module_permissions(), ensure_ascii=False),
        data_permissions=json.dumps(default_data_permissions(), ensure_ascii=False),
    )
    db.add(obj)
    write_browse_log(
        db,
        username=_current_username(),
        role=_current_role(),
        event_type="action",
        path="/api/admin/users",
        module="user_admin",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail=f"create user {username}",
    )
    db.commit()
    db.refresh(obj)
    return {
        "id": obj.id,
        "username": obj.username,
        "role": obj.role,
        "is_active": bool(obj.is_active),
        "module_permissions": default_module_permissions(),
        "data_permissions": default_data_permissions(),
    }


def admin_toggle_user_active(user_id: int, request: Request, db: Session = Depends(get_db)):
    _require_admin()
    row = db.query(User).filter(User.id == user_id).first()
    if not row:
        raise HTTPException(404, "user not found")
    if row.username == "xiaoyao":
        raise HTTPException(400, "xiaoyao 不允许停用")
    row.is_active = not bool(row.is_active)
    write_browse_log(
        db,
        username=_current_username(),
        role=_current_role(),
        event_type="action",
        path=f"/api/admin/users/{user_id}/toggle-active",
        module="user_admin",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail=f"set active={row.is_active} for {row.username}",
    )
    db.commit()
    return {"ok": True, "id": row.id, "is_active": bool(row.is_active)}


def admin_reset_user_password(user_id: int, body: UserResetPasswordBody, request: Request, db: Session = Depends(get_db)):
    _require_admin()
    row = db.query(User).filter(User.id == user_id).first()
    if not row:
        raise HTTPException(404, "user not found")
    if len(str(body.password or "")) < 4:
        raise HTTPException(400, "password 至少 4 位")
    row.password_hash = hash_password(body.password)
    write_browse_log(
        db,
        username=_current_username(),
        role=_current_role(),
        event_type="action",
        path=f"/api/admin/users/{user_id}/reset-password",
        module="user_admin",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail=f"reset password for {row.username}",
    )
    db.commit()
    return {"ok": True}


def admin_update_user(user_id: int, body: UserUpdateBody, request: Request, db: Session = Depends(get_db)):
    _require_admin()
    row = db.query(User).filter(User.id == user_id).first()
    if not row:
        raise HTTPException(404, "user not found")
    if row.username == "xiaoyao" and body.role and (body.role or "").strip().lower() != "admin":
        raise HTTPException(400, "xiaoyao 角色不允许修改")
    changes = []
    if body.role is not None:
        next_role = (body.role or "").strip().lower()
        if next_role not in {"admin", "user"}:
            raise HTTPException(400, "role 必须是 admin 或 user")
        if row.role != next_role:
            row.role = next_role
            changes.append(f"role={next_role}")
    if body.password is not None:
        next_pwd = str(body.password or "")
        if len(next_pwd) < 4:
            raise HTTPException(400, "password 至少 4 位")
        row.password_hash = hash_password(next_pwd)
        changes.append("password=updated")
    if (row.role or "user").strip().lower() != "admin":
        if body.module_permissions is not None:
            normalized_modules = normalize_module_permissions(body.module_permissions)
            row.module_permissions = json.dumps(normalized_modules, ensure_ascii=False)
            changes.append(f"module_permissions={','.join(normalized_modules)}")
        if body.data_permissions is not None:
            normalized_data = normalize_data_permissions(body.data_permissions)
            row.data_permissions = json.dumps(normalized_data, ensure_ascii=False)
            changes.append("data_permissions=" + ",".join(f"{k}:{v}" for k, v in sorted(normalized_data.items())))
    if not changes:
        raise HTTPException(400, "无可更新字段")
    write_browse_log(
        db,
        username=_current_username(),
        role=_current_role(),
        event_type="action",
        path=f"/api/admin/users/{user_id}",
        module="user_admin",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail=f"update user {row.username}: {'; '.join(changes)}",
    )
    db.commit()
    module_permissions, data_permissions = serialize_user_permissions(row)
    if (row.role or "user").strip().lower() == "admin":
        module_permissions = default_module_permissions()
        data_permissions = default_data_permissions()
    return {
        "ok": True,
        "id": row.id,
        "username": row.username,
        "role": row.role,
        "is_active": bool(row.is_active),
        "module_permissions": module_permissions,
        "data_permissions": data_permissions,
    }


def admin_delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    _require_admin()
    row = db.query(User).filter(User.id == user_id).first()
    if not row:
        raise HTTPException(404, "user not found")
    if row.username == "xiaoyao":
        raise HTTPException(400, "xiaoyao 不允许删除")
    if row.username == _current_username():
        raise HTTPException(400, "当前登录账号不允许删除")
    deleted_username = row.username
    db.delete(row)
    write_browse_log(
        db,
        username=_current_username(),
        role=_current_role(),
        event_type="action",
        path=f"/api/admin/users/{user_id}",
        module="user_admin",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail=f"delete user {deleted_username}",
    )
    db.commit()
    return {"ok": True}
