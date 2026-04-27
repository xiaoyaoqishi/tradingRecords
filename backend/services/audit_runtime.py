from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from core import context
from core.config import settings
from core.db import get_db
import core.db as core_db
from core.security import ensure_admin
from models import BrowseLog

CN_TZ = settings.timezone

EVENT_TYPE_ZH_MAP = {
    "page_view": "浏览",
    "action": "操作",
}

MODULE_ZH_MAP = {
    "auth": "登录认证",
    "audit": "审计日志",
    "monitor_home": "网站监控首页",
    "monitor_site": "站点巡检",
    "user_admin": "用户管理",
    "notes": "笔记应用",
    "trading": "交易记录",
}


def _current_username() -> str:
    return context.username()


def _current_role() -> str:
    return context.role()


def _current_is_admin() -> bool:
    return context.is_admin()


def _require_admin() -> None:
    ensure_admin(is_admin=_current_is_admin())


class BrowseTrackBody(BaseModel):
    path: str
    module: Optional[str] = None
    detail: Optional[str] = None


def _to_cn_datetime_text(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CN_TZ).strftime("%Y-%m-%d %H:%M:%S")


def _parse_cn_datetime_filter(raw: Optional[str], *, end_of_day: bool = False) -> Optional[datetime]:
    text_val = (raw or "").strip()
    if not text_val:
        return None
    formats = [
        ("%Y-%m-%d %H:%M:%S", False),
        ("%Y/%m/%d %H:%M:%S", False),
        ("%Y-%m-%d", True),
        ("%Y/%m/%d", True),
    ]
    parsed = None
    for fmt, is_date_only in formats:
        try:
            parsed = datetime.strptime(text_val, fmt)
            if is_date_only:
                parsed = parsed.replace(
                    hour=23 if end_of_day else 0,
                    minute=59 if end_of_day else 0,
                    second=59 if end_of_day else 0,
                )
            break
        except ValueError:
            continue
    if parsed is None:
        raise HTTPException(400, "date_from/date_to 格式应为 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS（中国时间）")
    return parsed.replace(tzinfo=CN_TZ).astimezone(timezone.utc).replace(tzinfo=None)


def _to_cn_detail_text(*, detail: Optional[str], event_type: str, path: str) -> str:
    raw = (detail or "").strip()
    if raw == "login success":
        return "登录成功"
    if raw == "logout":
        return "退出登录"
    if raw == "open monitor app":
        return "打开网站监控应用"
    if raw.startswith("create user "):
        return f"创建用户：{raw.replace('create user ', '', 1)}"
    if raw.startswith("set active="):
        return raw.replace("set active=", "设置启用状态=").replace(" for ", "，用户：")
    if raw.startswith("reset password for "):
        return f"重置密码：{raw.replace('reset password for ', '', 1)}"
    if raw.startswith("update user "):
        return raw.replace("update user ", "更新用户：", 1)
    if raw.startswith("delete user "):
        return f"删除用户：{raw.replace('delete user ', '', 1)}"
    if raw:
        if re.search(r"[\u4e00-\u9fff]", raw):
            return raw
        if event_type == "page_view":
            return f"浏览页面：{path or '/'}"
        return f"执行操作：{path or '/'}"
    if event_type == "page_view":
        return f"浏览页面：{path or '/'}"
    return f"执行操作：{path or '/'}"


def write_browse_log(
    db: Session,
    *,
    username: str,
    role: str,
    event_type: str,
    path: str,
    module: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    normalized_role = (role or "").strip().lower() or "user"
    if normalized_role == "admin":
        return
    db.add(
        BrowseLog(
            username=(username or "").strip() or "unknown",
            role=normalized_role,
            event_type=(event_type or "").strip() or "action",
            path=(path or "").strip() or "/",
            module=(module or "").strip() or None,
            ip=(ip or "").strip() or None,
            user_agent=(user_agent or "").strip() or None,
            detail=(detail or "").strip() or None,
        )
    )


def write_action_log(request: Request, *, path: str, detail: Optional[str] = None) -> None:
    db = core_db.SessionLocal()
    try:
        write_browse_log(
            db,
            username=_current_username(),
            role=_current_role(),
            event_type="action",
            path=path,
            module="audit",
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            detail=detail,
        )
        db.commit()
    finally:
        db.close()


def audit_track(body: BrowseTrackBody, request: Request, db: Session = Depends(get_db)):
    write_browse_log(
        db,
        username=_current_username(),
        role=_current_role(),
        event_type="page_view",
        path=(body.path or "/").strip() or "/",
        module=(body.module or "").strip() or None,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail=body.detail,
    )
    db.commit()
    return {"ok": True}


def audit_logs(
    username: Optional[str] = None,
    module: Optional[str] = None,
    event_type: Optional[str] = None,
    keyword: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    _require_admin()
    q = db.query(BrowseLog)
    q = q.filter(func.lower(BrowseLog.role) != "admin")
    if username:
        q = q.filter(BrowseLog.username == username)
    if module:
        q = q.filter(BrowseLog.module == module)
    if event_type:
        q = q.filter(BrowseLog.event_type == event_type)
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        q = q.filter(
            or_(
                BrowseLog.path.ilike(kw),
                BrowseLog.detail.ilike(kw),
                BrowseLog.username.ilike(kw),
                BrowseLog.module.ilike(kw),
            )
        )
    dt_from = _parse_cn_datetime_filter(date_from, end_of_day=False)
    dt_to = _parse_cn_datetime_filter(date_to, end_of_day=True)
    if dt_from:
        q = q.filter(BrowseLog.created_at >= dt_from)
    if dt_to:
        q = q.filter(BrowseLog.created_at <= dt_to)
    total = q.count()
    rows = q.order_by(BrowseLog.created_at.desc(), BrowseLog.id.desc()).offset((page - 1) * size).limit(size).all()
    return {
        "items": [
            {
                "id": x.id,
                "username": x.username,
                "role": x.role,
                "event_type": x.event_type,
                "event_type_zh": EVENT_TYPE_ZH_MAP.get((x.event_type or "").strip(), "其他"),
                "path": x.path,
                "module": x.module,
                "module_zh": MODULE_ZH_MAP.get((x.module or "").strip(), x.module or "未分类"),
                "ip": x.ip,
                "user_agent": x.user_agent,
                "detail": x.detail,
                "detail_zh": _to_cn_detail_text(detail=x.detail, event_type=x.event_type or "", path=x.path or "/"),
                "created_at": x.created_at,
                "created_at_zh": _to_cn_datetime_text(x.created_at),
            }
            for x in rows
        ],
        "total": total,
        "page": page,
        "size": size,
    }


def delete_audit_log(log_id: int, db: Session = Depends(get_db)):
    _require_admin()
    row = db.query(BrowseLog).filter(BrowseLog.id == log_id).first()
    if not row:
        raise HTTPException(404, "记录不存在")
    db.delete(row)
    db.commit()
    return {"ok": True}
