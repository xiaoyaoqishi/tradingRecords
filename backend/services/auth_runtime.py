from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from auth import create_token, hash_password, load_legacy_credentials, save_credentials, verify_password, verify_token
from core import context
from core.config import settings
import core.db as core_db
from models import User
from services.audit_runtime import write_action_log, write_browse_log

DEV_MODE = settings.dev_mode
AUTH_COOKIE = settings.auth_cookie
AUTH_WHITELIST = set(settings.auth_whitelist)
COOKIE_SECURE = settings.cookie_secure
ALL_USER_MODULES = {"trading", "notes", "ledger"}
READ_WRITE_VALUES = {"read_write", "read_only"}


def _safe_json_load(raw: Any, fallback: Any):
    try:
        parsed = json.loads(raw or "")
        return parsed if isinstance(parsed, type(fallback)) else fallback
    except Exception:
        return fallback


def default_module_permissions() -> list[str]:
    return sorted(ALL_USER_MODULES)


def default_data_permissions() -> dict[str, str]:
    return {module: "read_write" for module in ALL_USER_MODULES}


def normalize_module_permissions(value: Any) -> list[str]:
    if value is None:
        return default_module_permissions()
    source = value if isinstance(value, list) else []
    out: list[str] = []
    seen = set()
    for item in source:
        key = str(item or "").strip().lower()
        if key in ALL_USER_MODULES and key not in seen:
            seen.add(key)
            out.append(key)
    return out or default_module_permissions()


def normalize_data_permissions(value: Any) -> dict[str, str]:
    out: dict[str, str] = default_data_permissions()
    if not isinstance(value, dict):
        return out
    for module, mode in value.items():
        key = str(module or "").strip().lower()
        val = str(mode or "").strip().lower()
        if key in ALL_USER_MODULES and val in READ_WRITE_VALUES:
            out[key] = val
    return out


def serialize_user_permissions(user: User) -> tuple[list[str], dict[str, str]]:
    modules = normalize_module_permissions(_safe_json_load(user.module_permissions, []))
    data_perms = normalize_data_permissions(_safe_json_load(user.data_permissions, {}))
    return modules, data_perms


def api_module_from_path(path: str):
    if path.startswith("/api/ledger"):
        return "ledger"
    if path.startswith("/api/notebooks") or path.startswith("/api/notes") or path.startswith("/api/todos"):
        return "notes"
    trading_prefixes = (
        "/api/trades",
        "/api/reviews",
        "/api/review-sessions",
        "/api/trade-plans",
        "/api/knowledge-items",
        "/api/trade-brokers",
        "/api/trade-review-taxonomy",
        "/api/recycle",
    )
    if path.startswith(trading_prefixes):
        return "trading"
    return None


def migrate_legacy_auth_to_users() -> None:
    db = core_db.SessionLocal()
    try:
        has_users = db.query(User).first() is not None
        if has_users:
            return
        legacy = load_legacy_credentials() or {}
        legacy_hash = str(legacy.get("password") or "").strip()
        if legacy_hash and ":" in legacy_hash:
            password_hash = legacy_hash
        else:
            return
        db.add(
            User(
                username="xiaoyao",
                password_hash=password_hash,
                role="admin",
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token_username = "xiaoyao"
        token_role = "admin"
        token_is_admin = True
        token_modules = default_module_permissions()
        token_data_permissions = default_data_permissions()
        if DEV_MODE:
            request.state.username = token_username
            request.state.role = token_role
            request.state.is_admin = token_is_admin
            request.state.module_permissions = token_modules
            request.state.data_permissions = token_data_permissions
        elif request.url.path.startswith("/api/"):
            token = request.cookies.get(AUTH_COOKIE)
            parsed_username = verify_token(token) if token else None
            if request.url.path not in AUTH_WHITELIST and not parsed_username:
                return JSONResponse(status_code=401, content={"detail": "未登录"})
            if parsed_username:
                db = core_db.SessionLocal()
                try:
                    user = db.query(User).filter(User.username == parsed_username, User.is_active == True).first()  # noqa: E712
                finally:
                    db.close()
                if not user and request.url.path not in AUTH_WHITELIST:
                    return JSONResponse(status_code=401, content={"detail": "账号不可用"})
                if user:
                    token_username = user.username
                    token_role = (user.role or "user").strip().lower()
                    token_is_admin = token_role == "admin"
                    token_modules, token_data_permissions = serialize_user_permissions(user)

            if not token_is_admin and request.url.path not in AUTH_WHITELIST:
                module_key = api_module_from_path(request.url.path)
                if module_key and module_key not in token_modules:
                    return JSONResponse(status_code=403, content={"detail": "该模块对当前用户不可见"})
                if module_key and request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
                    if token_data_permissions.get(module_key, "read_write") == "read_only":
                        return JSONResponse(status_code=403, content={"detail": "该模块为只读权限，禁止写入"})
            request.state.username = token_username
            request.state.role = token_role
            request.state.is_admin = token_is_admin
            request.state.module_permissions = token_modules
            request.state.data_permissions = token_data_permissions
        username_token = context.current_username.set(token_username)
        role_token = context.current_role.set(token_role)
        is_admin_token = context.current_is_admin.set(token_is_admin)
        try:
            return await call_next(request)
        finally:
            context.current_username.reset(username_token)
            context.current_role.reset(role_token)
            context.current_is_admin.reset(is_admin_token)


class LoginBody(BaseModel):
    username: str
    password: str


def auth_check(request: Request):
    if DEV_MODE:
        return {
            "authenticated": True,
            "username": "xiaoyao",
            "role": "admin",
            "is_admin": True,
            "module_permissions": default_module_permissions(),
            "data_permissions": default_data_permissions(),
        }
    token = request.cookies.get(AUTH_COOKIE)
    parsed_username = verify_token(token) if token else None
    if not parsed_username:
        return {"authenticated": False}
    db = core_db.SessionLocal()
    try:
        user = db.query(User).filter(User.username == parsed_username, User.is_active == True).first()  # noqa: E712
        if not user:
            return {"authenticated": False}
        role = (user.role or "user").strip().lower()
        module_permissions, data_permissions = serialize_user_permissions(user)
        if role == "admin":
            module_permissions = default_module_permissions()
            data_permissions = default_data_permissions()
        return {
            "authenticated": True,
            "username": user.username,
            "role": role,
            "is_admin": role == "admin",
            "module_permissions": module_permissions,
            "data_permissions": data_permissions,
        }
    finally:
        db.close()


def auth_setup(body: LoginBody):
    db = core_db.SessionLocal()
    try:
        if db.query(User).first():
            raise HTTPException(400, "账号已存在，无法重复初始化")
        db.add(
            User(
                username="xiaoyao",
                password_hash=hash_password(body.password),
                role="admin",
                is_active=True,
            )
        )
        db.commit()
        save_credentials("xiaoyao", body.password)
        return {"ok": True, "username": "xiaoyao", "role": "admin"}
    finally:
        db.close()


def auth_login(body: LoginBody, response: Response, request: Request):
    db = core_db.SessionLocal()
    login_username = (body.username or "").strip()
    login_role = "user"
    try:
        user = db.query(User).filter(User.username == body.username).first()
        if not user:
            if db.query(User).count() == 0:
                raise HTTPException(400, "请先初始化账号 (POST /api/auth/setup)")
            raise HTTPException(401, "用户名或密码错误")
        if not bool(user.is_active):
            raise HTTPException(403, "账号已停用")
        password_ok = verify_password(user.password_hash, body.password)
        if (not password_ok) and (":" not in str(user.password_hash or "")):
            if str(user.password_hash or "") == body.password:
                user.password_hash = hash_password(body.password)
                password_ok = True
        if not password_ok:
            raise HTTPException(401, "用户名或密码错误")
        login_username = user.username
        login_role = (user.role or "user").strip().lower() or "user"
        token = create_token(user.username)
        db.commit()
        try:
            write_browse_log(
                db,
                username=login_username,
                role=login_role,
                event_type="action",
                path="/api/auth/login",
                module="auth",
                ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                detail="login success",
            )
            db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()
    cookie_secure = bool(COOKIE_SECURE and request.url.scheme == "https")
    response.set_cookie(
        AUTH_COOKIE,
        token,
        max_age=7 * 86400,
        httponly=True,
        samesite="lax",
        path="/",
        secure=cookie_secure,
    )
    return {"ok": True, "username": login_username, "role": login_role, "is_admin": login_role == "admin"}


def auth_logout(response: Response, request: Request):
    write_action_log(request, path="/api/auth/logout", detail="logout")
    response.delete_cookie(AUTH_COOKIE, path="/")
    return {"ok": True}
