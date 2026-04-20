from fastapi import Depends, HTTPException, Query, Request, Response, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text, func, or_, event
from sqlalchemy.orm import with_loader_criteria
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import json
import os
import uuid
import shutil
import threading
import time as _time
import re
import html
import hashlib
import xml.etree.ElementTree as ET
import random
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
import psutil
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup

from core import context
from core.config import settings
from core.security import ensure_admin, normalize_owner_role

DEV_MODE = settings.dev_mode

from core.db import engine, get_db, Base, SessionLocal
from models import (
    Trade, TradeReview, TradeSourceMetadata, Review, ReviewTradeLink, ReviewSession, ReviewSessionTradeLink,
    TradePlan, TradePlanTradeLink, TradePlanReviewSessionLink, KnowledgeItem,
    Notebook, Note, NoteLink, TodoItem, TradeBroker, User, BrowseLog, MonitorSite, MonitorSiteResult,
)
from schemas import (
    TradeCreate, TradeUpdate, TradeResponse,
    TradePasteImportRequest, TradePasteImportResponse, TradePasteImportError, TradePositionResponse,
    TradeSearchOptionItemResponse, TradeSearchOptionsResponse,
    TradeReviewUpsert, TradeReviewResponse, TradeReviewTaxonomyResponse,
    TradeSourceMetadataUpsert, TradeSourceMetadataResponse,
    TradeBrokerCreate, TradeBrokerUpdate, TradeBrokerResponse,
    ReviewCreate, ReviewUpdate, ReviewResponse, ReviewTradeLinksPayload, ReviewTradeLinkResponse,
    ReviewSessionCreate, ReviewSessionUpdate, ReviewSessionResponse, ReviewSessionTradeLinksPayload, ReviewSessionCreateFromSelection,
    TradePlanCreate, TradePlanUpdate, TradePlanResponse, TradePlanTradeLinksPayload, TradePlanReviewSessionLinksPayload,
    KnowledgeItemCreate, KnowledgeItemUpdate, KnowledgeItemResponse,
    NotebookCreate, NotebookUpdate, NotebookResponse,
    NoteCreate, NoteUpdate, NoteResponse,
    TodoCreate, TodoUpdate, TodoResponse,
)
from auth import (
    load_credentials,
    save_credentials,
    check_login,
    create_token,
    verify_token,
    load_legacy_credentials,
    hash_password,
    verify_password,
)
from trade_review_taxonomy import trade_review_taxonomy
from trading.source_service import (
    extract_source_from_notes as _source_extract_source_from_notes,
    apply_source_keyword_filter as _source_apply_source_keyword_filter,
    attach_trade_view_fields as _source_attach_trade_view_fields,
    list_trade_sources as _source_list_trade_sources,
    upsert_trade_source_metadata_for_import as _source_upsert_trade_source_metadata_for_import,
)
from trading.analytics_service import build_trade_analytics
from trading.import_service import import_paste_trades_staged
from trading.review_session_service import (
    attach_review_session_link_fields as _review_session_attach_link_fields,
    sync_review_session_trade_links as _review_session_sync_trade_links,
    normalize_review_session_scope as _review_session_normalize_scope,
    normalize_review_session_kind as _review_session_normalize_kind,
    normalize_review_selection_mode as _review_session_normalize_selection_mode,
    normalize_review_selection_target as _review_session_normalize_selection_target,
)
from trading.trade_plan_service import (
    attach_trade_plan_link_fields as _trade_plan_attach_link_fields,
    sync_trade_plan_trade_links as _trade_plan_sync_trade_links,
    sync_trade_plan_review_session_links as _trade_plan_sync_review_session_links,
    normalize_trade_plan_status as _trade_plan_normalize_status,
    assert_trade_plan_status_transition as _trade_plan_assert_status_transition,
)
from trading.knowledge_service import (
    list_knowledge_items as _knowledge_list_knowledge_items,
    list_knowledge_categories as _knowledge_list_categories,
    normalize_knowledge_payload as _knowledge_normalize_payload,
    normalize_related_note_ids as _knowledge_normalize_related_note_ids,
    sync_knowledge_item_note_links as _knowledge_sync_note_links,
    attach_knowledge_item_related_notes as _knowledge_attach_related_notes,
)
from trading.tag_service import (
    normalize_tag_list as _normalize_tag_list,
    serialize_legacy_tags as _serialize_legacy_tags,
    sync_trade_review_tags as _sync_trade_review_tags,
    sync_knowledge_item_tags as _sync_knowledge_item_tags,
    attach_trade_review_tags as _attach_trade_review_tags,
    attach_knowledge_item_tags as _attach_knowledge_item_tags,
)

ROLE_SCOPED_MODELS = (
    Trade,
    ReviewSession,
    TradePlan,
    KnowledgeItem,
    Notebook,
    Note,
    TodoItem,
    TradeBroker,
)


def _current_username() -> str:
    return context.username()


def _current_role() -> str:
    return context.role()


def _current_is_admin() -> bool:
    return context.is_admin()


def _owner_role_value_for_create() -> str:
    return "admin" if _current_is_admin() else "user"


def _require_admin():
    ensure_admin(is_admin=_current_is_admin())


def _owner_role_filter_for_admin(model, owner_role: Optional[str]):
    if not _current_is_admin():
        return None
    role = normalize_owner_role(owner_role)
    if role:
        return model.owner_role == role
    return None


@event.listens_for(Session, "do_orm_execute")
def _apply_owner_role_scope(execute_state):
    if not execute_state.is_select:
        return
    if _current_is_admin():
        return
    statement = execute_state.statement
    for model in ROLE_SCOPED_MODELS:
        statement = statement.options(
            with_loader_criteria(model, lambda cls: cls.owner_role == "user", include_aliases=True)
        )
    execute_state.statement = statement


def _column_names(db: Session, table: str) -> set[str]:
    rows = db.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def _table_exists(db: Session, table: str) -> bool:
    row = db.execute(
        text("SELECT name FROM sqlite_master WHERE type = 'table' AND name = :name"),
        {"name": table},
    ).fetchone()
    return bool(row)


def _ensure_sqlite_column(db: Session, table: str, column: str, ddl_fragment: str):
    cols = _column_names(db, table)
    if cols and column not in cols:
        db.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_fragment}"))


def _migrate_legacy_schema():
    db = SessionLocal()
    try:
        if _table_exists(db, "users"):
            user_cols = _column_names(db, "users")
            if "password_hash" not in user_cols:
                db.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))
                if "password" in user_cols:
                    db.execute(
                        text(
                            "UPDATE users SET password_hash = password "
                            "WHERE (password_hash IS NULL OR password_hash = '') AND password IS NOT NULL"
                        )
                    )
            _ensure_sqlite_column(db, "users", "role", "VARCHAR(20) DEFAULT 'user'")
            _ensure_sqlite_column(db, "users", "is_active", "BOOLEAN DEFAULT 1")
            _ensure_sqlite_column(db, "users", "created_at", "DATETIME")
            _ensure_sqlite_column(db, "users", "updated_at", "DATETIME")
            db.execute(text("UPDATE users SET role='user' WHERE role IS NULL OR role=''"))
            db.execute(text("UPDATE users SET is_active=1 WHERE is_active IS NULL"))
            db.execute(text("UPDATE users SET role='admin' WHERE username='xiaoyao'"))

        notebook_cols = _column_names(db, "notebooks")
        if "parent_id" not in notebook_cols:
            db.execute(text("ALTER TABLE notebooks ADD COLUMN parent_id INTEGER"))
        if "sort_order" not in notebook_cols:
            db.execute(text("ALTER TABLE notebooks ADD COLUMN sort_order INTEGER DEFAULT 0"))
        _ensure_sqlite_column(db, "notebooks", "owner_role", "VARCHAR(20) DEFAULT 'admin'")
        note_cols = _column_names(db, "notes")
        if "is_deleted" not in note_cols:
            db.execute(text("ALTER TABLE notes ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
        if "deleted_at" not in note_cols:
            db.execute(text("ALTER TABLE notes ADD COLUMN deleted_at DATETIME"))
        _ensure_sqlite_column(db, "notes", "owner_role", "VARCHAR(20) DEFAULT 'admin'")
        todo_cols = _column_names(db, "todo_items")
        if "source_anchor_text" not in todo_cols:
            db.execute(text("ALTER TABLE todo_items ADD COLUMN source_anchor_text TEXT"))
        if "due_at" not in todo_cols:
            db.execute(text("ALTER TABLE todo_items ADD COLUMN due_at DATETIME"))
        if "reminder_at" not in todo_cols:
            db.execute(text("ALTER TABLE todo_items ADD COLUMN reminder_at DATETIME"))
        _ensure_sqlite_column(db, "todo_items", "owner_role", "VARCHAR(20) DEFAULT 'admin'")
        review_cols = _column_names(db, "reviews")
        if "title" not in review_cols:
            db.execute(text("ALTER TABLE reviews ADD COLUMN title VARCHAR(200)"))
        if "review_scope" not in review_cols:
            db.execute(text("ALTER TABLE reviews ADD COLUMN review_scope VARCHAR(30) DEFAULT 'periodic'"))
        if "focus_topic" not in review_cols:
            db.execute(text("ALTER TABLE reviews ADD COLUMN focus_topic VARCHAR(200)"))
        if "market_regime" not in review_cols:
            db.execute(text("ALTER TABLE reviews ADD COLUMN market_regime VARCHAR(100)"))
        if "tags" not in review_cols:
            db.execute(text("ALTER TABLE reviews ADD COLUMN tags TEXT"))
        if "action_items" not in review_cols:
            db.execute(text("ALTER TABLE reviews ADD COLUMN action_items TEXT"))
        if "research_notes" not in review_cols:
            db.execute(text("ALTER TABLE reviews ADD COLUMN research_notes TEXT"))
        if "is_favorite" not in review_cols:
            db.execute(text("ALTER TABLE reviews ADD COLUMN is_favorite BOOLEAN DEFAULT 0"))
        if "star_rating" not in review_cols:
            db.execute(text("ALTER TABLE reviews ADD COLUMN star_rating INTEGER"))
        trade_cols = _column_names(db, "trades")
        if "is_favorite" not in trade_cols:
            db.execute(text("ALTER TABLE trades ADD COLUMN is_favorite BOOLEAN DEFAULT 0"))
        if "star_rating" not in trade_cols:
            db.execute(text("ALTER TABLE trades ADD COLUMN star_rating INTEGER"))
        if "is_deleted" not in trade_cols:
            db.execute(text("ALTER TABLE trades ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
        if "deleted_at" not in trade_cols:
            db.execute(text("ALTER TABLE trades ADD COLUMN deleted_at DATETIME"))
        _ensure_sqlite_column(db, "trades", "owner_role", "VARCHAR(20) DEFAULT 'admin'")
        if _table_exists(db, "trade_brokers"):
            _ensure_sqlite_column(db, "trade_brokers", "is_deleted", "BOOLEAN DEFAULT 0")
            _ensure_sqlite_column(db, "trade_brokers", "deleted_at", "DATETIME")
            _ensure_sqlite_column(db, "trade_brokers", "owner_role", "VARCHAR(20) DEFAULT 'admin'")
        if _table_exists(db, "knowledge_items"):
            _ensure_sqlite_column(db, "knowledge_items", "is_deleted", "BOOLEAN DEFAULT 0")
            _ensure_sqlite_column(db, "knowledge_items", "deleted_at", "DATETIME")
            _ensure_sqlite_column(db, "knowledge_items", "owner_role", "VARCHAR(20) DEFAULT 'admin'")
        if _table_exists(db, "review_sessions"):
            _ensure_sqlite_column(db, "review_sessions", "review_kind", "VARCHAR(40) DEFAULT 'custom'")
            _ensure_sqlite_column(db, "review_sessions", "review_scope", "VARCHAR(40) DEFAULT 'custom'")
            _ensure_sqlite_column(db, "review_sessions", "selection_mode", "VARCHAR(40) DEFAULT 'manual'")
            _ensure_sqlite_column(db, "review_sessions", "selection_basis", "TEXT DEFAULT ''")
            _ensure_sqlite_column(db, "review_sessions", "review_goal", "TEXT DEFAULT ''")
            _ensure_sqlite_column(db, "review_sessions", "market_regime", "VARCHAR(100)")
            _ensure_sqlite_column(db, "review_sessions", "summary", "TEXT")
            _ensure_sqlite_column(db, "review_sessions", "repeated_errors", "TEXT")
            _ensure_sqlite_column(db, "review_sessions", "next_focus", "TEXT")
            _ensure_sqlite_column(db, "review_sessions", "action_items", "TEXT")
            _ensure_sqlite_column(db, "review_sessions", "content", "TEXT")
            _ensure_sqlite_column(db, "review_sessions", "research_notes", "TEXT")
            _ensure_sqlite_column(db, "review_sessions", "tags", "TEXT")
            _ensure_sqlite_column(db, "review_sessions", "filter_snapshot_json", "TEXT")
            _ensure_sqlite_column(db, "review_sessions", "is_favorite", "BOOLEAN DEFAULT 0")
            _ensure_sqlite_column(db, "review_sessions", "star_rating", "INTEGER")
            _ensure_sqlite_column(db, "review_sessions", "is_deleted", "BOOLEAN DEFAULT 0")
            _ensure_sqlite_column(db, "review_sessions", "deleted_at", "DATETIME")
            _ensure_sqlite_column(db, "review_sessions", "owner_role", "VARCHAR(20) DEFAULT 'admin'")
        if _table_exists(db, "trade_plans"):
            _ensure_sqlite_column(db, "trade_plans", "status", "VARCHAR(20) DEFAULT 'draft'")
            _ensure_sqlite_column(db, "trade_plans", "symbol", "VARCHAR(50)")
            _ensure_sqlite_column(db, "trade_plans", "contract", "VARCHAR(50)")
            _ensure_sqlite_column(db, "trade_plans", "direction_bias", "VARCHAR(20)")
            _ensure_sqlite_column(db, "trade_plans", "setup_type", "VARCHAR(80)")
            _ensure_sqlite_column(db, "trade_plans", "market_regime", "VARCHAR(100)")
            _ensure_sqlite_column(db, "trade_plans", "entry_zone", "TEXT")
            _ensure_sqlite_column(db, "trade_plans", "stop_loss_plan", "TEXT")
            _ensure_sqlite_column(db, "trade_plans", "target_plan", "TEXT")
            _ensure_sqlite_column(db, "trade_plans", "invalid_condition", "TEXT")
            _ensure_sqlite_column(db, "trade_plans", "thesis", "TEXT")
            _ensure_sqlite_column(db, "trade_plans", "risk_notes", "TEXT")
            _ensure_sqlite_column(db, "trade_plans", "execution_checklist", "TEXT")
            _ensure_sqlite_column(db, "trade_plans", "priority", "VARCHAR(20) DEFAULT 'medium'")
            _ensure_sqlite_column(db, "trade_plans", "tags", "TEXT")
            _ensure_sqlite_column(db, "trade_plans", "source_ref", "VARCHAR(200)")
            _ensure_sqlite_column(db, "trade_plans", "post_result_summary", "TEXT")
            _ensure_sqlite_column(db, "trade_plans", "research_notes", "TEXT")
            _ensure_sqlite_column(db, "trade_plans", "is_deleted", "BOOLEAN DEFAULT 0")
            _ensure_sqlite_column(db, "trade_plans", "deleted_at", "DATETIME")
            _ensure_sqlite_column(db, "trade_plans", "owner_role", "VARCHAR(20) DEFAULT 'admin'")
        for table in (
            "trades",
            "review_sessions",
            "trade_plans",
            "knowledge_items",
            "trade_brokers",
            "notebooks",
            "notes",
            "todo_items",
        ):
            if _table_exists(db, table):
                db.execute(text(f"UPDATE {table} SET owner_role='admin' WHERE owner_role IS NULL OR owner_role=''"))
        db.commit()
    finally:
        db.close()




def _migrate_reviews_to_review_sessions():
    db = SessionLocal()
    try:
        if not _table_exists(db, "review_sessions"):
            return
        has_review_rows = db.query(Review).first() is not None
        has_review_session_rows = db.query(ReviewSession).first() is not None
        if not has_review_rows or has_review_session_rows:
            return

        review_rows = db.query(Review).order_by(Review.id.asc()).all()
        for row in review_rows:
            obj = ReviewSession(
                title=row.title or f"{row.review_date} {row.review_type}",
                review_kind="period" if (row.review_scope or "periodic") == "periodic" else "custom",
                review_scope=_review_session_normalize_scope(row.review_scope),
                selection_mode="manual",
                selection_basis=row.focus_topic or f"legacy review #{row.id}",
                review_goal=row.summary or "legacy migration",
                market_regime=row.market_regime,
                summary=row.summary,
                repeated_errors=row.repeated_errors,
                next_focus=row.next_focus,
                action_items=row.action_items,
                content=row.content,
                research_notes=row.research_notes,
                tags_text=row.tags_text,
                filter_snapshot_json=None,
                is_favorite=bool(row.is_favorite),
                star_rating=row.star_rating,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            db.add(obj)
            db.flush()

            trade_links = (
                db.query(ReviewTradeLink)
                .filter(ReviewTradeLink.review_id == row.id)
                .order_by(ReviewTradeLink.id.asc())
                .all()
            )
            for idx, link in enumerate(trade_links):
                db.add(
                    ReviewSessionTradeLink(
                        review_session_id=obj.id,
                        trade_id=link.trade_id,
                        role=link.role,
                        note=link.notes,
                        sort_order=idx,
                    )
                )
        db.commit()
    finally:
        db.close()




def _init_default_notebooks():
    db = SessionLocal()
    try:
        if db.query(Notebook).count() == 0:
            db.add_all([
                Notebook(name="日记本", icon="📔", sort_order=0, owner_role="admin"),
                Notebook(name="文档", icon="📄", sort_order=1, owner_role="admin"),
            ])
            db.commit()
    finally:
        db.close()




def _migrate_legacy_auth_to_users():
    db = SessionLocal()
    try:
        has_users = db.query(User).first() is not None
        if has_users:
            return
        legacy = load_legacy_credentials() or {}
        legacy_hash = str(legacy.get("password") or "").strip()
        if legacy_hash and ":" in legacy_hash:
            password_hash = legacy_hash
        else:
            # no legacy credential: keep setup flow available
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



TODO_PRIORITIES = {"low", "medium", "high"}


def _normalize_todo_priority(priority: Optional[str]) -> str:
    val = (priority or "medium").strip().lower()
    if val not in TODO_PRIORITIES:
        raise HTTPException(400, "priority 必须是 low / medium / high")
    return val

AUTH_COOKIE = settings.auth_cookie
AUTH_WHITELIST = set(settings.auth_whitelist)
COOKIE_SECURE = settings.cookie_secure
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
                parsed = parsed.replace(hour=23 if end_of_day else 0, minute=59 if end_of_day else 0, second=59 if end_of_day else 0)
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


def _write_browse_log(
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
):
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


def _write_action_log(request: Request, *, path: str, detail: Optional[str] = None):
    db = SessionLocal()
    try:
        _write_browse_log(
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


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token_username = "xiaoyao"
        token_role = "admin"
        token_is_admin = True
        if DEV_MODE:
            request.state.username = token_username
            request.state.role = token_role
            request.state.is_admin = token_is_admin
        elif request.url.path.startswith("/api/"):
            token = request.cookies.get(AUTH_COOKIE)
            parsed_username = verify_token(token) if token else None
            if request.url.path not in AUTH_WHITELIST and not parsed_username:
                return JSONResponse(status_code=401, content={"detail": "未登录"})
            if parsed_username:
                db = SessionLocal()
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
            request.state.username = token_username
            request.state.role = token_role
            request.state.is_admin = token_is_admin
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


class UserCreateBody(BaseModel):
    username: str
    password: str


class UserResetPasswordBody(BaseModel):
    password: str


class UserUpdateBody(BaseModel):
    role: Optional[str] = None
    password: Optional[str] = None


class BrowseTrackBody(BaseModel):
    path: str
    module: Optional[str] = None
    detail: Optional[str] = None


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


def auth_check(request: Request):
    if DEV_MODE:
        return {"authenticated": True, "username": "xiaoyao", "role": "admin", "is_admin": True}
    token = request.cookies.get(AUTH_COOKIE)
    parsed_username = verify_token(token) if token else None
    if not parsed_username:
        return {"authenticated": False}
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == parsed_username, User.is_active == True).first()  # noqa: E712
        if not user:
            return {"authenticated": False}
        role = (user.role or "user").strip().lower()
        return {"authenticated": True, "username": user.username, "role": role, "is_admin": role == "admin"}
    finally:
        db.close()


def auth_setup(body: LoginBody):
    db = SessionLocal()
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
        # keep legacy auth file in sync for compatibility with older deploy scripts
        save_credentials("xiaoyao", body.password)
        return {"ok": True, "username": "xiaoyao", "role": "admin"}
    finally:
        db.close()


def auth_login(body: LoginBody, response: Response, request: Request):
    db = SessionLocal()
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
            # tolerate legacy plaintext password from older deployments
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
            _write_browse_log(
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
    _write_action_log(request, path="/api/auth/logout", detail="logout")
    response.delete_cookie(AUTH_COOKIE, path="/")
    return {"ok": True}


def admin_list_users(db: Session = Depends(get_db)):
    _require_admin()
    rows = db.query(User).order_by(User.created_at.desc(), User.id.desc()).all()
    return [
        {
            "id": x.id,
            "username": x.username,
            "role": x.role,
            "is_active": bool(x.is_active),
            "created_at": x.created_at,
            "updated_at": x.updated_at,
        }
        for x in rows
    ]


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
    obj = User(username=username, password_hash=hash_password(password), role="user", is_active=True)
    db.add(obj)
    _write_browse_log(
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
    return {"id": obj.id, "username": obj.username, "role": obj.role, "is_active": bool(obj.is_active)}


def admin_toggle_user_active(user_id: int, request: Request, db: Session = Depends(get_db)):
    _require_admin()
    row = db.query(User).filter(User.id == user_id).first()
    if not row:
        raise HTTPException(404, "user not found")
    if row.username == "xiaoyao":
        raise HTTPException(400, "xiaoyao 不允许停用")
    row.is_active = not bool(row.is_active)
    _write_browse_log(
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
    _write_browse_log(
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
    if not changes:
        raise HTTPException(400, "无可更新字段")
    _write_browse_log(
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
    return {"ok": True, "id": row.id, "username": row.username, "role": row.role, "is_active": bool(row.is_active)}


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
    _write_browse_log(
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


def audit_track(body: BrowseTrackBody, request: Request, db: Session = Depends(get_db)):
    _write_browse_log(
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


# ── Upload ──

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"}


async def upload_file(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"不支持的文件格式: {ext}")
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"url": f"/api/uploads/{filename}"}


def get_upload(filename: str):
    safe = os.path.basename(filename)
    path = os.path.join(UPLOAD_DIR, safe)
    if not os.path.exists(path):
        raise HTTPException(404, "File not found")
    return FileResponse(path)


# ── Trade ──

PASTE_TRADE_HEADERS = [
    "交易日期", "合约", "买/卖", "投机（一般）/套保/套利", "成交价",
    "手数", "成交额", "开/平", "手续费", "平仓盈亏",
]


def _normalize_contract_symbol(contract: str) -> str:
    c = (contract or "").strip()
    m = re.match(r"([A-Za-z]+)", c)
    if m:
        return m.group(1).upper()
    return c


def _parse_cn_date(value: str) -> date:
    s = str(value or "").strip()
    if not s:
        raise ValueError("交易日期为空")
    if re.fullmatch(r"\d+(\.\d+)?", s):
        n = float(s)
        # Excel serial date (1900 date system)
        if n > 20000:
            return date(1899, 12, 30) + timedelta(days=int(n))
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"无法识别交易日期: {s}")


def _parse_float(value: str, field: str) -> float:
    s = str(value or "").replace("\xa0", " ").strip().replace(",", "")
    if s in {"", "-", "--", "—", "——", "null", "None"}:
        return 0.0
    try:
        return float(s)
    except Exception as exc:
        raise ValueError(f"{field}格式错误: {value}") from exc


def _map_direction(v: str) -> str:
    s = str(v or "").replace("\xa0", " ").strip()
    if s in {"买", "买入", "多", "做多"}:
        return "做多"
    if s in {"卖", "卖出", "空", "做空"}:
        return "做空"
    raise ValueError(f"买/卖无法识别: {v}")


def _map_open_close(v: str) -> str:
    s = str(v or "").replace("\xa0", " ").strip()
    if "平" in s:
        return "closed"
    if "开" in s:
        return "open"
    raise ValueError(f"开/平无法识别: {v}")


def _parse_paste_row(cells: List[str], broker: Optional[str]) -> Trade:
    normalized_cells = list(cells or [])
    # 兼容无日期粘贴：仅当录入9列时，默认补当天日期为第一列。
    if len(normalized_cells) == 9:
        normalized_cells = [date.today().isoformat(), *normalized_cells]
    if len(normalized_cells) < 10:
        raise ValueError("列数不足，期望10列；若无交易日期可录入9列自动补当天")
    trade_day = _parse_cn_date(normalized_cells[0])
    contract = str(normalized_cells[1] or "").strip()
    if not contract:
        raise ValueError("合约为空")
    direction = _map_direction(normalized_cells[2])
    category = str(normalized_cells[3] or "").strip() or None
    open_price = _parse_float(normalized_cells[4], "成交价")
    quantity = _parse_float(normalized_cells[5], "手数")
    if quantity <= 0:
        raise ValueError("手数必须大于0")
    _turnover = _parse_float(normalized_cells[6], "成交额")
    status = _map_open_close(normalized_cells[7])
    commission = _parse_float(normalized_cells[8], "手续费")
    pnl = _parse_float(normalized_cells[9], "平仓盈亏")
    open_time = datetime.combine(trade_day, datetime.min.time()).replace(hour=9, minute=0, second=0)
    close_time = None
    close_price = None
    if status == "closed":
        close_time = datetime.combine(trade_day, datetime.min.time()).replace(hour=15, minute=0, second=0)
        close_price = open_price
    note_parts = []
    if broker:
        note_parts.append(f"来源券商: {broker}")
    note_parts.append("来源: 日结单粘贴导入")
    return Trade(
        trade_date=trade_day,
        instrument_type="期货",
        symbol=_normalize_contract_symbol(contract),
        contract=contract,
        category=category,
        direction=direction,
        open_time=open_time,
        close_time=close_time,
        open_price=open_price,
        close_price=close_price,
        quantity=quantity,
        commission=commission,
        pnl=pnl,
        status=status,
        notes=" | ".join(note_parts),
        owner_role=_owner_role_value_for_create(),
    )


def _position_side(direction: str, status: str) -> str:
    # 开仓: 买开->做多, 卖开->做空
    # 平仓: 买平->平空(做空持仓), 卖平->平多(做多持仓)
    if status == "open":
        return "做多" if direction == "做多" else "做空"
    return "做空" if direction == "做多" else "做多"


def _state_key(symbol: str, side: str) -> str:
    return f"{symbol}::{side}"


def _state_key_contract(symbol: str, contract: Optional[str], side: str) -> str:
    c = re.sub(r"\s+", "", (contract or "").strip()).upper()
    return f"{symbol}::{c}::{side}"


def _ensure_symbol_state(
    state: Dict[str, Dict[str, Any]],
    symbol: str,
    side: str,
    contract: Optional[str],
    trade_day: date,
):
    key = _state_key(symbol, side)
    if key not in state:
        state[key] = {
            "symbol": symbol,
            "side": side,
            "contract": contract,
            "quantity": 0.0,
            "avg_open_price": 0.0,
            "open_since": None,
            "last_trade_date": trade_day,
        }
    st = state[key]
    if contract:
        st["contract"] = contract
    st["last_trade_date"] = trade_day
    return st


def _apply_fill_to_state(state: Dict[str, Dict[str, Any]], fill: Trade):
    symbol = _normalize_contract_symbol(fill.contract or fill.symbol or "")
    side = _position_side(fill.direction, fill.status)
    st = _ensure_symbol_state(state, symbol, side, fill.contract, fill.trade_date)
    qty = float(fill.quantity or 0)
    if qty <= 0:
        raise ValueError("手数必须大于0")
    prev_qty = float(st["quantity"])

    if fill.status == "closed":
        # 平仓必须能匹配到对应方向持仓，且不能超平
        if prev_qty <= 0:
            raise ValueError(f"{symbol} {side} 平仓失败：当前无对应持仓")
        if qty - prev_qty > 1e-9:
            raise ValueError(f"{symbol} {side} 平仓手数超出持仓")
        remain = prev_qty - qty
        st["quantity"] = remain if remain > 1e-9 else 0.0
        if st["quantity"] <= 0:
            st["avg_open_price"] = 0.0
            st["open_since"] = None
        return

    # 开仓：同方向加权均价
    next_qty = prev_qty + qty
    prev_cost = float(st["avg_open_price"]) * prev_qty
    st["avg_open_price"] = (prev_cost + fill.open_price * qty) / next_qty
    st["quantity"] = next_qty
    if st["open_since"] is None:
        st["open_since"] = fill.trade_date


def _build_position_state_from_db(db: Session, source_keyword: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    state: Dict[str, Dict[str, Any]] = {}
    q = db.query(Trade).filter(Trade.is_deleted == False, Trade.status == "open")  # noqa: E712
    q = _apply_source_keyword_filter(q, source_keyword)
    rows = q.order_by(Trade.open_time.asc(), Trade.id.asc()).all()
    for t in rows:
        symbol = _normalize_contract_symbol(t.contract or t.symbol or "")
        side = t.direction
        st = _ensure_symbol_state(state, symbol, side, t.contract, t.trade_date)
        prev_qty = float(st["quantity"])
        add_qty = float(t.quantity or 0)
        if add_qty <= 0:
            continue
        total_qty = prev_qty + add_qty
        prev_cost = float(st["avg_open_price"]) * prev_qty
        st["avg_open_price"] = (prev_cost + float(t.open_price or 0) * add_qty) / total_qty
        st["quantity"] = total_qty
        if st["open_since"] is None:
            st["open_since"] = t.trade_date
        if t.open_time and (st["last_trade_date"] is None or t.trade_date >= st["last_trade_date"]):
            st["last_trade_date"] = t.trade_date
    return state


def _build_position_state_from_db_with_owner_role(
    db: Session,
    source_keyword: Optional[str] = None,
    owner_role: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    state: Dict[str, Dict[str, Any]] = {}
    q = db.query(Trade).filter(Trade.is_deleted == False, Trade.status == "open")  # noqa: E712
    role_filter = _owner_role_filter_for_admin(Trade, owner_role)
    if role_filter is not None:
        q = q.filter(role_filter)
    q = _apply_source_keyword_filter(q, source_keyword)
    rows = q.order_by(Trade.open_time.asc(), Trade.id.asc()).all()
    for t in rows:
        symbol = _normalize_contract_symbol(t.contract or t.symbol or "")
        side = t.direction
        st = _ensure_symbol_state(state, symbol, side, t.contract, t.trade_date)
        prev_qty = float(st["quantity"])
        add_qty = float(t.quantity or 0)
        if add_qty <= 0:
            continue
        total_qty = prev_qty + add_qty
        prev_cost = float(st["avg_open_price"]) * prev_qty
        st["avg_open_price"] = (prev_cost + float(t.open_price or 0) * add_qty) / total_qty
        st["quantity"] = total_qty
        if st["open_since"] is None:
            st["open_since"] = t.trade_date
        if t.open_time and (st["last_trade_date"] is None or t.trade_date >= st["last_trade_date"]):
            st["last_trade_date"] = t.trade_date
    return state


def _append_note(base: Optional[str], extra: str) -> str:
    b = (base or "").strip()
    if not b:
        return extra
    return f"{b} | {extra}"


def _extract_source_from_notes(note: Optional[str]) -> Dict[str, Optional[str]]:
    return _source_extract_source_from_notes(note)


def _attach_trade_view_fields(db: Session, rows: List[Trade]) -> List[Trade]:
    return _source_attach_trade_view_fields(db, rows)


def _apply_source_keyword_filter(q, source_keyword: Optional[str]):
    return _source_apply_source_keyword_filter(q, source_keyword)


def _upsert_trade_source_metadata_for_import(
    db: Session,
    trade: Trade,
    broker: Optional[str],
    source_label: Optional[str] = None,
):
    _source_upsert_trade_source_metadata_for_import(
        db,
        trade,
        broker=broker,
        source_label=source_label,
    )


def _copy_trade_for_closed_part(src: Trade, close_qty: float, close_price: float, close_time: datetime, close_commission: float, close_pnl: float) -> Trade:
    open_commission_part = (float(src.commission or 0) * close_qty / float(src.quantity or 1))
    return Trade(
        trade_date=src.trade_date,
        instrument_type=src.instrument_type,
        symbol=src.symbol,
        contract=src.contract,
        category=src.category,
        direction=src.direction,
        open_time=src.open_time,
        close_time=close_time,
        open_price=src.open_price,
        close_price=close_price,
        quantity=close_qty,
        margin=src.margin,
        commission=round(open_commission_part + close_commission, 6),
        slippage=src.slippage,
        pnl=round(close_pnl, 6),
        pnl_points=src.pnl_points,
        holding_duration=src.holding_duration,
        is_overnight=src.is_overnight,
        trading_session=src.trading_session,
        status="closed",
        is_main_contract=src.is_main_contract,
        is_near_delivery=src.is_near_delivery,
        is_contract_switch=src.is_contract_switch,
        is_high_volatility=src.is_high_volatility,
        is_near_data_release=src.is_near_data_release,
        entry_logic=src.entry_logic,
        exit_logic=src.exit_logic,
        strategy_type=src.strategy_type,
        market_condition=src.market_condition,
        timeframe=src.timeframe,
        core_signal=src.core_signal,
        stop_loss_plan=src.stop_loss_plan,
        target_plan=src.target_plan,
        followed_plan=src.followed_plan,
        is_planned=src.is_planned,
        is_impulsive=src.is_impulsive,
        is_chasing=src.is_chasing,
        is_holding_loss=src.is_holding_loss,
        is_early_profit=src.is_early_profit,
        is_extended_stop=src.is_extended_stop,
        is_overweight=src.is_overweight,
        is_revenge=src.is_revenge,
        is_emotional=src.is_emotional,
        mental_state=src.mental_state,
        physical_state=src.physical_state,
        pre_opportunity=src.pre_opportunity,
        pre_win_reason=src.pre_win_reason,
        pre_risk=src.pre_risk,
        during_match_expectation=src.during_match_expectation,
        during_plan_changed=src.during_plan_changed,
        post_quality=src.post_quality,
        post_repeat=src.post_repeat,
        post_root_cause=src.post_root_cause,
        post_replicable=src.post_replicable,
        error_tags=src.error_tags,
        review_note=src.review_note,
        notes=_append_note(src.notes, "来源: 自动平仓拆分"),
        owner_role=src.owner_role or _owner_role_value_for_create(),
    )


def _apply_close_fill_to_db(db: Session, fill: Trade, broker: Optional[str] = None):
    # SessionLocal 默认 autoflush=False，导入时会连续多次查询 open 持仓。
    # 这里先 flush，确保前一次平仓变更（status/quantity）对本次匹配可见。
    db.flush()
    symbol = _normalize_contract_symbol(fill.contract or fill.symbol or "")
    contract_norm = re.sub(r"\s+", "", (fill.contract or "").strip()).upper()
    close_side = _position_side(fill.direction, "closed")
    close_time = fill.close_time or datetime.combine(fill.trade_date, datetime.min.time()).replace(hour=15)
    q = db.query(Trade).filter(
        Trade.is_deleted == False,  # noqa: E712
        Trade.instrument_type == "期货",
        Trade.symbol == symbol,
        Trade.direction == close_side,
        Trade.status == "open",
        Trade.owner_role == (fill.owner_role or _owner_role_value_for_create()),
        Trade.trade_date <= fill.trade_date,
        or_(Trade.open_time.is_(None), Trade.open_time <= close_time),
    )
    if contract_norm:
        q = q.filter(func.upper(func.replace(func.trim(Trade.contract), " ", "")) == contract_norm)
    if broker:
        q = q.filter(Trade.notes.contains(f"来源券商: {broker}"))
    open_rows = q.order_by(Trade.open_time.asc(), Trade.id.asc()).all()
    remaining = float(fill.quantity or 0)
    if remaining <= 0:
        raise ValueError("平仓手数必须大于0")
    total_open = sum(float(x.quantity or 0) for x in open_rows)
    if total_open + 1e-9 < remaining:
        raise ValueError(f"{symbol} {close_side} 平仓失败：可匹配持仓不足（平仓时间早于对应开仓时间）")

    close_price = float(fill.open_price or 0)
    close_commission_total = float(fill.commission or 0)
    close_pnl_total = float(fill.pnl or 0)
    close_qty_total = float(fill.quantity or 1)
    affected_rows: List[Trade] = []

    for row in open_rows:
        if remaining <= 1e-9:
            break
        row_qty = float(row.quantity or 0)
        if row_qty <= 0:
            continue
        take = min(row_qty, remaining)
        ratio = take / close_qty_total
        close_commission_part = close_commission_total * ratio
        close_pnl_part = close_pnl_total * ratio

        if abs(take - row_qty) <= 1e-9:
            row.status = "closed"
            row.close_price = close_price
            row.close_time = close_time
            row.pnl = round(close_pnl_part, 6)
            row.commission = round(float(row.commission or 0) + close_commission_part, 6)
            row.notes = _append_note(row.notes, "来源: 自动平仓匹配")
            affected_rows.append(row)
        else:
            remaining_qty = row_qty - take
            closed_row = _copy_trade_for_closed_part(
                row,
                close_qty=take,
                close_price=close_price,
                close_time=close_time,
                close_commission=close_commission_part,
                close_pnl=close_pnl_part,
            )
            db.add(closed_row)
            affected_rows.append(closed_row)
            open_commission_total = float(row.commission or 0)
            row.quantity = round(remaining_qty, 6)
            row.commission = round(open_commission_total * (remaining_qty / row_qty), 6)
            row.notes = _append_note(row.notes, "部分平仓后自动拆分")
            affected_rows.append(row)
        remaining -= take
    return affected_rows


def import_trades_from_paste(payload: TradePasteImportRequest, db: Session = Depends(get_db)):
    try:
        return import_paste_trades_staged(
            db,
            raw_text=payload.raw_text,
            broker=payload.broker,
            paste_headers=PASTE_TRADE_HEADERS,
            parse_paste_row=_parse_paste_row,
            normalize_contract_symbol=_normalize_contract_symbol,
            position_side=_position_side,
            state_key_contract=_state_key_contract,
            apply_close_fill_to_db=_apply_close_fill_to_db,
            upsert_trade_source_metadata_for_import=_upsert_trade_source_metadata_for_import,
            error_cls=TradePasteImportError,
            response_cls=TradePasteImportResponse,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))


def list_trade_positions(
    symbol: Optional[str] = None,
    source_keyword: Optional[str] = None,
    owner_role: Optional[str] = None,
    db: Session = Depends(get_db),
):
    state = _build_position_state_from_db_with_owner_role(db, source_keyword=source_keyword, owner_role=owner_role)
    rows = []
    for _, st in state.items():
        qty = float(st.get("quantity") or 0)
        if qty < 1e-9:
            continue
        if symbol and st["symbol"] != symbol:
            continue
        rows.append(
            TradePositionResponse(
                symbol=st["symbol"],
                contract=st.get("contract"),
                net_quantity=round(qty, 6),
                side=st.get("side") or "做多",
                avg_open_price=round(float(st.get("avg_open_price") or 0), 4),
                open_since=st.get("open_since"),
                last_trade_date=st.get("last_trade_date"),
            )
        )
    rows.sort(key=lambda x: (x.symbol, x.side))
    return rows


def list_trades(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    instrument_type: Optional[str] = None,
    symbol: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    strategy_type: Optional[str] = None,
    source_keyword: Optional[str] = None,
    is_favorite: Optional[bool] = None,
    min_star_rating: Optional[int] = Query(None, ge=1, le=5),
    max_star_rating: Optional[int] = Query(None, ge=1, le=5),
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "desc",
    owner_role: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Trade).filter(Trade.is_deleted == False)  # noqa: E712
    role_filter = _owner_role_filter_for_admin(Trade, owner_role)
    if role_filter is not None:
        q = q.filter(role_filter)
    if date_from:
        q = q.filter(Trade.trade_date >= date_from)
    if date_to:
        q = q.filter(Trade.trade_date <= date_to)
    if instrument_type:
        q = q.filter(Trade.instrument_type == instrument_type)
    if symbol:
        q = q.filter(Trade.symbol == symbol)
    if direction:
        q = q.filter(Trade.direction == direction)
    if status:
        q = q.filter(Trade.status == status)
    if strategy_type:
        q = q.filter(Trade.strategy_type == strategy_type)
    if is_favorite is not None:
        q = q.filter(Trade.is_favorite == is_favorite)
    if min_star_rating is not None:
        q = q.filter(Trade.star_rating >= min_star_rating)
    if max_star_rating is not None:
        q = q.filter(Trade.star_rating <= max_star_rating)
    q = _apply_source_keyword_filter(q, source_keyword)
    if sort_by not in {None, "updated_at", "star_rating"}:
        raise HTTPException(400, "sort_by must be one of: updated_at, star_rating")
    if sort_order not in {"asc", "desc"}:
        raise HTTPException(400, "sort_order must be one of: asc, desc")
    order_desc = sort_order != "asc"
    if sort_by == "updated_at":
        order_expr = Trade.updated_at.desc() if order_desc else Trade.updated_at.asc()
        q = q.order_by(order_expr, Trade.id.desc())
    elif sort_by == "star_rating":
        order_expr = Trade.star_rating.desc() if order_desc else Trade.star_rating.asc()
        q = q.order_by(order_expr, Trade.updated_at.desc(), Trade.id.desc())
    else:
        q = q.order_by(Trade.open_time.desc())
    rows = q.offset((page - 1) * size).limit(size).all()
    return _attach_trade_view_fields(db, rows)


def _parse_include_ids(include_ids: Optional[str]) -> List[int]:
    if not include_ids:
        return []
    out: List[int] = []
    seen = set()
    for part in str(include_ids).split(","):
        raw = part.strip()
        if not raw:
            continue
        if not raw.isdigit():
            continue
        val = int(raw)
        if val <= 0 or val in seen:
            continue
        seen.add(val)
        out.append(val)
    return out


def list_trade_search_options(
    q: Optional[str] = None,
    symbol: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    include_ids: Optional[str] = None,
    owner_role: Optional[str] = None,
    limit: int = Query(30, ge=1, le=50),
    db: Session = Depends(get_db),
):
    include_trade_ids = _parse_include_ids(include_ids)

    query = (
        db.query(Trade)
        .filter(Trade.is_deleted == False)  # noqa: E712
        .outerjoin(TradeSourceMetadata, TradeSourceMetadata.trade_id == Trade.id)
    )
    role_filter = _owner_role_filter_for_admin(Trade, owner_role)
    if role_filter is not None:
        query = query.filter(role_filter)
    if symbol:
        query = query.filter(Trade.symbol == symbol)
    if date_from:
        query = query.filter(Trade.trade_date >= date_from)
    if date_to:
        query = query.filter(Trade.trade_date <= date_to)
    if status:
        query = query.filter(Trade.status == status)

    keyword = (q or "").strip()
    if keyword:
        conds = [
            Trade.symbol.contains(keyword.upper()),
            Trade.contract.contains(keyword),
            Trade.notes.contains(keyword),
            TradeSourceMetadata.broker_name.contains(keyword),
            TradeSourceMetadata.source_label.contains(keyword),
        ]
        if keyword.isdigit():
            conds.append(Trade.id == int(keyword))
        query = query.filter(or_(*conds))

    rows = query.order_by(Trade.open_time.desc(), Trade.id.desc()).limit(limit).all()
    ordered_rows = _attach_trade_view_fields(db, rows)
    collected_ids = {x.id for x in ordered_rows if x.id}

    missing_include_ids = [tid for tid in include_trade_ids if tid not in collected_ids]
    if missing_include_ids:
        include_q = db.query(Trade).filter(Trade.id.in_(missing_include_ids), Trade.is_deleted == False)  # noqa: E712
        include_role_filter = _owner_role_filter_for_admin(Trade, owner_role)
        if include_role_filter is not None:
            include_q = include_q.filter(include_role_filter)
        include_rows = include_q.order_by(Trade.open_time.desc(), Trade.id.desc()).all()
        include_rows = _attach_trade_view_fields(db, include_rows)
        include_map = {x.id: x for x in include_rows if x.id}
        for trade_id in missing_include_ids:
            row = include_map.get(trade_id)
            if row:
                ordered_rows.append(row)
                collected_ids.add(row.id)

    trade_ids = [x.id for x in ordered_rows if x.id]
    review_conclusion_by_trade_id: Dict[int, Optional[str]] = {}
    if trade_ids:
        review_rows = db.query(TradeReview).filter(TradeReview.trade_id.in_(trade_ids)).all()
        for row in review_rows:
            review_conclusion_by_trade_id[row.trade_id] = row.review_conclusion

    items = [
        TradeSearchOptionItemResponse(
            trade_id=row.id,
            trade_date=row.trade_date,
            symbol=row.symbol,
            contract=row.contract,
            direction=row.direction,
            quantity=row.quantity,
            open_price=row.open_price,
            close_price=row.close_price,
            status=row.status,
            pnl=row.pnl,
            source_display=getattr(row, "source_display", None),
            has_trade_review=bool(getattr(row, "has_trade_review", False)),
            review_conclusion=review_conclusion_by_trade_id.get(row.id),
        )
        for row in ordered_rows
    ]
    return TradeSearchOptionsResponse(items=items)


def count_trades(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    instrument_type: Optional[str] = None,
    symbol: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    strategy_type: Optional[str] = None,
    source_keyword: Optional[str] = None,
    is_favorite: Optional[bool] = None,
    min_star_rating: Optional[int] = Query(None, ge=1, le=5),
    max_star_rating: Optional[int] = Query(None, ge=1, le=5),
    owner_role: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Trade).filter(Trade.is_deleted == False)  # noqa: E712
    role_filter = _owner_role_filter_for_admin(Trade, owner_role)
    if role_filter is not None:
        q = q.filter(role_filter)
    if date_from:
        q = q.filter(Trade.trade_date >= date_from)
    if date_to:
        q = q.filter(Trade.trade_date <= date_to)
    if instrument_type:
        q = q.filter(Trade.instrument_type == instrument_type)
    if symbol:
        q = q.filter(Trade.symbol == symbol)
    if direction:
        q = q.filter(Trade.direction == direction)
    if status:
        q = q.filter(Trade.status == status)
    if strategy_type:
        q = q.filter(Trade.strategy_type == strategy_type)
    if is_favorite is not None:
        q = q.filter(Trade.is_favorite == is_favorite)
    if min_star_rating is not None:
        q = q.filter(Trade.star_rating >= min_star_rating)
    if max_star_rating is not None:
        q = q.filter(Trade.star_rating <= max_star_rating)
    q = _apply_source_keyword_filter(q, source_keyword)
    return {"total": q.count()}


def get_statistics(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    instrument_type: Optional[str] = None,
    symbol: Optional[str] = None,
    source_keyword: Optional[str] = None,
    owner_role: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Trade).filter(Trade.is_deleted == False, Trade.status == "closed")  # noqa: E712
    role_filter = _owner_role_filter_for_admin(Trade, owner_role)
    if role_filter is not None:
        q = q.filter(role_filter)
    if date_from:
        q = q.filter(Trade.trade_date >= date_from)
    if date_to:
        q = q.filter(Trade.trade_date <= date_to)
    if instrument_type:
        q = q.filter(Trade.instrument_type == instrument_type)
    if symbol:
        q = q.filter(Trade.symbol == symbol)
    q = _apply_source_keyword_filter(q, source_keyword)

    trades = q.all()
    empty = {
        "total": 0, "win_count": 0, "loss_count": 0,
        "win_rate": 0, "total_pnl": 0, "avg_pnl": 0,
        "max_pnl": 0, "min_pnl": 0, "avg_win": 0, "avg_loss": 0,
        "profit_loss_ratio": 0,
        "max_consecutive_wins": 0, "max_consecutive_losses": 0,
        "pnl_by_symbol": [], "pnl_by_strategy": [],
        "pnl_over_time": [], "error_tag_counts": [],
    }
    if not trades:
        return empty

    pnls = [t.pnl or 0 for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    max_cw = max_cl = cw = cl = 0
    for p in pnls:
        if p > 0:
            cw += 1; cl = 0; max_cw = max(max_cw, cw)
        elif p < 0:
            cl += 1; cw = 0; max_cl = max(max_cl, cl)
        else:
            cw = cl = 0

    sym_pnl: dict[str, float] = {}
    for t in trades:
        sym_pnl[t.symbol] = sym_pnl.get(t.symbol, 0) + (t.pnl or 0)

    strat: dict[str, dict] = {}
    for t in trades:
        if t.strategy_type:
            s = strat.setdefault(t.strategy_type, {"pnl": 0, "count": 0, "wins": 0})
            s["pnl"] += t.pnl or 0
            s["count"] += 1
            if (t.pnl or 0) > 0:
                s["wins"] += 1

    daily: dict[str, float] = {}
    for t in trades:
        d = str(t.trade_date)
        daily[d] = daily.get(d, 0) + (t.pnl or 0)

    cum = 0
    pnl_over_time = []
    for d in sorted(daily):
        cum += daily[d]
        pnl_over_time.append({"date": d, "daily_pnl": round(daily[d], 2), "cumulative_pnl": round(cum, 2)})

    err: dict[str, int] = {}
    for t in trades:
        if t.error_tags:
            try:
                for tag in json.loads(t.error_tags):
                    err[tag] = err.get(tag, 0) + 1
            except Exception:
                pass

    avg_w = round(sum(wins) / len(wins), 2) if wins else 0
    avg_l = round(sum(losses) / len(losses), 2) if losses else 0

    return {
        "total": len(trades),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": round(len(wins) / len(trades) * 100, 2),
        "total_pnl": round(sum(pnls), 2),
        "avg_pnl": round(sum(pnls) / len(pnls), 2),
        "max_pnl": round(max(pnls), 2),
        "min_pnl": round(min(pnls), 2),
        "avg_win": avg_w,
        "avg_loss": avg_l,
        "profit_loss_ratio": round(abs(avg_w / avg_l), 2) if avg_l else 0,
        "max_consecutive_wins": max_cw,
        "max_consecutive_losses": max_cl,
        "pnl_by_symbol": [{"symbol": k, "pnl": round(v, 2)} for k, v in sorted(sym_pnl.items(), key=lambda x: x[1], reverse=True)],
        "pnl_by_strategy": [
            {"strategy": k, "pnl": round(v["pnl"], 2), "count": v["count"],
             "win_rate": round(v["wins"] / v["count"] * 100, 2)}
            for k, v in strat.items()
        ],
        "pnl_over_time": pnl_over_time,
        "error_tag_counts": [{"tag": k, "count": v} for k, v in sorted(err.items(), key=lambda x: x[1], reverse=True)],
    }


def get_trade_analytics(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    instrument_type: Optional[str] = None,
    symbol: Optional[str] = None,
    source_keyword: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return build_trade_analytics(
        db,
        date_from=date_from,
        date_to=date_to,
        instrument_type=instrument_type,
        symbol=symbol,
        source_keyword=source_keyword,
        apply_source_keyword_filter=_apply_source_keyword_filter,
        attach_trade_view_fields=_attach_trade_view_fields,
        build_position_state_from_db=_build_position_state_from_db,
        extract_source_from_notes=_extract_source_from_notes,
    )


def create_trade(trade: TradeCreate, db: Session = Depends(get_db)):
    obj = Trade(**trade.model_dump(), owner_role=_owner_role_value_for_create())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _attach_trade_view_fields(db, [obj])[0]


def get_trade(trade_id: int, db: Session = Depends(get_db)):
    t = db.query(Trade).filter(Trade.id == trade_id, Trade.is_deleted == False).first()  # noqa: E712
    if not t:
        raise HTTPException(404, "Trade not found")
    return _attach_trade_view_fields(db, [t])[0]


def update_trade(trade_id: int, data: TradeUpdate, db: Session = Depends(get_db)):
    t = db.query(Trade).filter(Trade.id == trade_id, Trade.is_deleted == False).first()  # noqa: E712
    if not t:
        raise HTTPException(404, "Trade not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return _attach_trade_view_fields(db, [t])[0]


def delete_trade(trade_id: int, db: Session = Depends(get_db)):
    t = db.query(Trade).filter(Trade.id == trade_id, Trade.is_deleted == False).first()  # noqa: E712
    if not t:
        raise HTTPException(404, "Trade not found")
    t.is_deleted = True
    t.deleted_at = datetime.now()
    db.commit()
    return {"ok": True}


def list_trade_sources(owner_role: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Trade).filter(Trade.is_deleted == False)  # noqa: E712
    role_filter = _owner_role_filter_for_admin(Trade, owner_role)
    if role_filter is not None:
        q = q.filter(role_filter)
    rows = q.all()
    items = sorted({str(getattr(x, "source_display", "")).strip() for x in _attach_trade_view_fields(db, rows) if str(getattr(x, "source_display", "")).strip()})
    return {"items": items}


def list_trade_symbols(owner_role: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Trade.symbol).filter(Trade.is_deleted == False, Trade.symbol.isnot(None))  # noqa: E712
    role_filter = _owner_role_filter_for_admin(Trade, owner_role)
    if role_filter is not None:
        q = q.filter(role_filter)
    rows = q.distinct().order_by(Trade.symbol.asc()).all()
    items = [str(symbol).strip() for (symbol,) in rows if str(symbol or "").strip()]
    return {"items": items}


def get_trade_review_taxonomy():
    return TradeReviewTaxonomyResponse(**trade_review_taxonomy())


def get_trade_review(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(Trade).filter(Trade.id == trade_id, Trade.is_deleted == False).first()  # noqa: E712
    if not trade:
        raise HTTPException(404, "Trade not found")
    review = db.query(TradeReview).filter(TradeReview.trade_id == trade_id).first()
    if not review:
        raise HTTPException(404, "Trade review not found")
    return _attach_trade_review_tags(db, [review])[0]


def upsert_trade_review(trade_id: int, data: TradeReviewUpsert, db: Session = Depends(get_db)):
    trade = db.query(Trade).filter(Trade.id == trade_id, Trade.is_deleted == False).first()  # noqa: E712
    if not trade:
        raise HTTPException(404, "Trade not found")

    review = db.query(TradeReview).filter(TradeReview.trade_id == trade_id).first()
    if not review:
        review = TradeReview(trade_id=trade_id)
        db.add(review)

    payload = data.model_dump(exclude_unset=True)
    tags_raw = payload.pop("tags", None) if "tags" in payload else None
    legacy_tags_raw = payload.get("review_tags") if "review_tags" in payload else None
    for k, v in payload.items():
        setattr(review, k, v)

    should_sync_tags = tags_raw is not None or legacy_tags_raw is not None
    if should_sync_tags:
        tag_names = _normalize_tag_list(tags_raw if tags_raw is not None else legacy_tags_raw)
        review.review_tags = _serialize_legacy_tags(tag_names)
        db.flush()
        _sync_trade_review_tags(db, review.id, tag_names)

    db.commit()
    db.refresh(review)
    return _attach_trade_review_tags(db, [review])[0]


def delete_trade_review(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(Trade).filter(Trade.id == trade_id, Trade.is_deleted == False).first()  # noqa: E712
    if not trade:
        raise HTTPException(404, "Trade not found")
    review = db.query(TradeReview).filter(TradeReview.trade_id == trade_id).first()
    if not review:
        return {"ok": True}
    db.delete(review)
    db.commit()
    return {"ok": True}


def get_trade_source_metadata(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(Trade).filter(Trade.id == trade_id, Trade.is_deleted == False).first()  # noqa: E712
    if not trade:
        raise HTTPException(404, "Trade not found")

    row = db.query(TradeSourceMetadata).filter(TradeSourceMetadata.trade_id == trade_id).first()
    if row:
        return TradeSourceMetadataResponse(
            id=row.id,
            trade_id=row.trade_id,
            broker_name=row.broker_name,
            source_label=row.source_label,
            import_channel=row.import_channel,
            source_note_snapshot=row.source_note_snapshot,
            parser_version=row.parser_version,
            derived_from_notes=bool(row.derived_from_notes),
            created_at=row.created_at,
            updated_at=row.updated_at,
            exists_in_db=True,
        )

    parsed = _extract_source_from_notes(trade.notes)
    return TradeSourceMetadataResponse(
        trade_id=trade_id,
        broker_name=parsed["broker_name"],
        source_label=parsed["source_label"],
        import_channel=None,
        source_note_snapshot=trade.notes,
        parser_version=None,
        derived_from_notes=True,
        exists_in_db=False,
    )


def upsert_trade_source_metadata(trade_id: int, data: TradeSourceMetadataUpsert, db: Session = Depends(get_db)):
    trade = db.query(Trade).filter(Trade.id == trade_id, Trade.is_deleted == False).first()  # noqa: E712
    if not trade:
        raise HTTPException(404, "Trade not found")

    row = db.query(TradeSourceMetadata).filter(TradeSourceMetadata.trade_id == trade_id).first()
    if not row:
        row = TradeSourceMetadata(trade_id=trade_id)
        db.add(row)

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return TradeSourceMetadataResponse(
        id=row.id,
        trade_id=row.trade_id,
        broker_name=row.broker_name,
        source_label=row.source_label,
        import_channel=row.import_channel,
        source_note_snapshot=row.source_note_snapshot,
        parser_version=row.parser_version,
        derived_from_notes=bool(row.derived_from_notes),
        created_at=row.created_at,
        updated_at=row.updated_at,
        exists_in_db=True,
    )


def list_trade_brokers(owner_role: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(TradeBroker).filter(TradeBroker.is_deleted == False)  # noqa: E712
    role_filter = _owner_role_filter_for_admin(TradeBroker, owner_role)
    if role_filter is not None:
        q = q.filter(role_filter)
    return q.order_by(TradeBroker.updated_at.desc(), TradeBroker.id.desc()).all()


def create_trade_broker(data: TradeBrokerCreate, db: Session = Depends(get_db)):
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(400, "名称不能为空")
    existed = db.query(TradeBroker).filter(TradeBroker.name == name).first()
    if existed and not existed.is_deleted:
        raise HTTPException(400, "该名称已存在")
    if existed and existed.is_deleted:
        existed.is_deleted = False
        existed.deleted_at = None
        existed.account = (data.account or "").strip() or None
        existed.password = (data.password or "").strip() or None
        existed.extra_info = (data.extra_info or "").strip() or None
        existed.notes = (data.notes or "").strip() or None
        db.commit()
        db.refresh(existed)
        return existed
    obj = TradeBroker(
        name=name,
        account=(data.account or "").strip() or None,
        password=(data.password or "").strip() or None,
        extra_info=(data.extra_info or "").strip() or None,
        notes=(data.notes or "").strip() or None,
        owner_role=_owner_role_value_for_create(),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_trade_broker(broker_id: int, data: TradeBrokerUpdate, db: Session = Depends(get_db)):
    obj = db.query(TradeBroker).filter(TradeBroker.id == broker_id, TradeBroker.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(404, "券商不存在")
    payload = data.model_dump(exclude_unset=True)
    if "name" in payload:
        new_name = (payload.get("name") or "").strip()
        if not new_name:
            raise HTTPException(400, "名称不能为空")
        existed = db.query(TradeBroker).filter(TradeBroker.name == new_name, TradeBroker.id != broker_id).first()
        if existed:
            raise HTTPException(400, "该名称已存在")
        obj.name = new_name
    if "account" in payload:
        obj.account = (payload.get("account") or "").strip() or None
    if "password" in payload:
        obj.password = (payload.get("password") or "").strip() or None
    if "extra_info" in payload:
        obj.extra_info = (payload.get("extra_info") or "").strip() or None
    if "notes" in payload:
        obj.notes = (payload.get("notes") or "").strip() or None
    db.commit()
    db.refresh(obj)
    return obj


def delete_trade_broker(broker_id: int, db: Session = Depends(get_db)):
    obj = db.query(TradeBroker).filter(TradeBroker.id == broker_id, TradeBroker.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(404, "券商不存在")
    obj.is_deleted = True
    obj.deleted_at = datetime.now()
    db.commit()
    return {"ok": True}


# ── Knowledge ──


def list_knowledge_items(
    category: Optional[str] = None,
    status: Optional[str] = None,
    tag: Optional[str] = None,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    owner_role: Optional[str] = None,
    db: Session = Depends(get_db),
):
    scoped_owner_role = None
    role_filter = _owner_role_filter_for_admin(KnowledgeItem, owner_role)
    if role_filter is not None:
        scoped_owner_role = owner_role
    rows = _knowledge_list_knowledge_items(
        db,
        category=category,
        status=status,
        tag=tag,
        keyword=q,
        owner_role=scoped_owner_role,
        page=page,
        size=size,
    )
    rows = _attach_knowledge_item_tags(db, rows)
    return _knowledge_attach_related_notes(db, rows)


def list_knowledge_item_categories(owner_role: Optional[str] = None, db: Session = Depends(get_db)):
    _owner_role_filter_for_admin(KnowledgeItem, owner_role)
    return {"items": _knowledge_list_categories(db, owner_role=owner_role if owner_role in {"admin", "user"} else None)}


def create_knowledge_item(data: KnowledgeItemCreate, db: Session = Depends(get_db)):
    payload = _knowledge_normalize_payload(data.model_dump())
    tags_raw = payload.pop("tags", None) if "tags" in payload else None
    related_note_ids_raw = payload.pop("related_note_ids", None) if "related_note_ids" in payload else None
    obj = KnowledgeItem(**payload, owner_role=_owner_role_value_for_create())
    db.add(obj)
    db.flush()
    tag_names = _normalize_tag_list(tags_raw)
    related_note_ids = _knowledge_normalize_related_note_ids(related_note_ids_raw)
    obj.tags_text = _serialize_legacy_tags(tag_names)
    _sync_knowledge_item_tags(db, obj.id, tag_names)
    _knowledge_sync_note_links(db, obj.id, related_note_ids)
    db.commit()
    db.refresh(obj)
    rows = _attach_knowledge_item_tags(db, [obj])
    rows = _knowledge_attach_related_notes(db, rows)
    return rows[0]


def get_knowledge_item(item_id: int, db: Session = Depends(get_db)):
    obj = db.query(KnowledgeItem).filter(KnowledgeItem.id == item_id, KnowledgeItem.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(404, "Knowledge item not found")
    rows = _attach_knowledge_item_tags(db, [obj])
    rows = _knowledge_attach_related_notes(db, rows)
    return rows[0]


def update_knowledge_item(item_id: int, data: KnowledgeItemUpdate, db: Session = Depends(get_db)):
    obj = db.query(KnowledgeItem).filter(KnowledgeItem.id == item_id, KnowledgeItem.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(404, "Knowledge item not found")
    payload = _knowledge_normalize_payload(data.model_dump(exclude_unset=True))
    tags_raw = payload.pop("tags", None) if "tags" in payload else None
    related_note_ids_raw = payload.pop("related_note_ids", None) if "related_note_ids" in payload else None
    for k, v in payload.items():
        setattr(obj, k, v)
    if tags_raw is not None:
        tag_names = _normalize_tag_list(tags_raw)
        obj.tags_text = _serialize_legacy_tags(tag_names)
        db.flush()
        _sync_knowledge_item_tags(db, obj.id, tag_names)
    if related_note_ids_raw is not None:
        related_note_ids = _knowledge_normalize_related_note_ids(related_note_ids_raw)
        db.flush()
        _knowledge_sync_note_links(db, obj.id, related_note_ids)
    db.commit()
    db.refresh(obj)
    rows = _attach_knowledge_item_tags(db, [obj])
    rows = _knowledge_attach_related_notes(db, rows)
    return rows[0]


def delete_knowledge_item(item_id: int, db: Session = Depends(get_db)):
    obj = db.query(KnowledgeItem).filter(KnowledgeItem.id == item_id, KnowledgeItem.is_deleted == False).first()  # noqa: E712
    if not obj:
        raise HTTPException(404, "Knowledge item not found")
    obj.is_deleted = True
    obj.deleted_at = datetime.now()
    db.commit()
    return {"ok": True}


# ── Review ──


def _parse_tags_text(tags_text: Optional[str]) -> List[str]:
    return _normalize_tag_list(tags_text)


def _attach_review_session_fields(db: Session, rows: List[ReviewSession]) -> List[ReviewSession]:
    rows = _review_session_attach_link_fields(db, rows)
    for row in rows:
        setattr(row, "tags", _parse_tags_text(row.tags_text))
    return rows


def _review_session_to_legacy_response(row: ReviewSession) -> Dict[str, Any]:
    review_date = (row.created_at.date() if row.created_at else date.today())
    scope = row.review_scope or "custom"
    review_type = "custom"
    if scope == "periodic":
        review_type = "weekly"
    return {
        "id": row.id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "review_type": review_type,
        "review_date": review_date,
        "title": row.title,
        "review_scope": scope,
        "focus_topic": row.selection_basis,
        "market_regime": row.market_regime,
        "tags": getattr(row, "tags", _parse_tags_text(row.tags_text)),
        "tags_text": row.tags_text,
        "best_trade": None,
        "worst_trade": None,
        "discipline_violated": None,
        "loss_acceptable": None,
        "execution_score": None,
        "tomorrow_avoid": None,
        "profit_source": None,
        "loss_source": None,
        "continue_trades": None,
        "reduce_trades": None,
        "repeated_errors": row.repeated_errors,
        "next_focus": row.next_focus,
        "profit_from_skill": None,
        "best_strategy": None,
        "profit_eating_behavior": None,
        "adjust_symbols": None,
        "adjust_position": None,
        "pause_patterns": None,
        "action_items": row.action_items,
        "content": row.content,
        "research_notes": row.research_notes,
        "summary": row.summary,
        "is_favorite": row.is_favorite,
        "star_rating": row.star_rating,
        "trade_links": [
            {
                "id": x.id,
                "review_id": row.id,
                "trade_id": x.trade_id,
                "role": x.role,
                "notes": x.note,
                "trade_summary": getattr(x, "trade_summary", None),
                "created_at": x.created_at,
                "updated_at": x.updated_at,
            }
            for x in getattr(row, "trade_links", [])
        ],
        "linked_trade_ids": [x.trade_id for x in getattr(row, "trade_links", [])],
    }


def _apply_trade_filters(
    q,
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    instrument_type: Optional[str] = None,
    symbol: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    strategy_type: Optional[str] = None,
    source_keyword: Optional[str] = None,
    is_favorite: Optional[bool] = None,
    min_star_rating: Optional[int] = None,
    max_star_rating: Optional[int] = None,
    owner_role: Optional[str] = None,
):
    q = q.filter(Trade.is_deleted == False)  # noqa: E712
    role_filter = _owner_role_filter_for_admin(Trade, owner_role)
    if role_filter is not None:
        q = q.filter(role_filter)
    if date_from:
        q = q.filter(Trade.trade_date >= date_from)
    if date_to:
        q = q.filter(Trade.trade_date <= date_to)
    if instrument_type:
        q = q.filter(Trade.instrument_type == instrument_type)
    if symbol:
        q = q.filter(Trade.symbol == symbol)
    if direction:
        q = q.filter(Trade.direction == direction)
    if status:
        q = q.filter(Trade.status == status)
    if strategy_type:
        q = q.filter(Trade.strategy_type == strategy_type)
    if is_favorite is not None:
        q = q.filter(Trade.is_favorite == is_favorite)
    if min_star_rating is not None:
        q = q.filter(Trade.star_rating >= min_star_rating)
    if max_star_rating is not None:
        q = q.filter(Trade.star_rating <= max_star_rating)
    q = _apply_source_keyword_filter(q, source_keyword)
    return q


def _build_trade_ids_from_filter(db: Session, filter_params: Dict[str, Any]) -> List[int]:
    q = db.query(Trade).filter(Trade.is_deleted == False)  # noqa: E712
    q = _apply_trade_filters(
        q,
        date_from=filter_params.get("date_from"),
        date_to=filter_params.get("date_to"),
        instrument_type=filter_params.get("instrument_type"),
        symbol=filter_params.get("symbol"),
        direction=filter_params.get("direction"),
        status=filter_params.get("status"),
        strategy_type=filter_params.get("strategy_type"),
        source_keyword=filter_params.get("source_keyword"),
        is_favorite=filter_params.get("is_favorite"),
        min_star_rating=filter_params.get("min_star_rating"),
        max_star_rating=filter_params.get("max_star_rating"),
        owner_role=filter_params.get("owner_role"),
    )
    rows = q.order_by(Trade.open_time.desc(), Trade.id.desc()).all()
    return [x.id for x in rows if x.id]


def _create_review_session_from_payload(db: Session, payload: Dict[str, Any], trade_links: List[Dict[str, Any]]) -> ReviewSession:
    tags_raw = payload.pop("tags", None) if "tags" in payload else None
    payload["review_kind"] = _review_session_normalize_kind(payload.get("review_kind"))
    payload["review_scope"] = _review_session_normalize_scope(payload.get("review_scope"))
    payload["selection_mode"] = _review_session_normalize_selection_mode(payload.get("selection_mode"))
    payload["owner_role"] = payload.get("owner_role") or _owner_role_value_for_create()
    obj = ReviewSession(**payload)
    db.add(obj)
    db.flush()
    tag_names = _normalize_tag_list(tags_raw)
    obj.tags_text = _serialize_legacy_tags(tag_names)
    _review_session_sync_trade_links(db, obj, trade_links)
    db.commit()
    db.refresh(obj)
    return _attach_review_session_fields(db, [obj])[0]


def list_review_sessions(
    review_kind: Optional[str] = None,
    review_scope: Optional[str] = None,
    selection_mode: Optional[str] = None,
    tag: Optional[str] = None,
    is_favorite: Optional[bool] = None,
    min_star_rating: Optional[int] = Query(None, ge=1, le=5),
    max_star_rating: Optional[int] = Query(None, ge=1, le=5),
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "desc",
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    owner_role: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(ReviewSession).filter(ReviewSession.is_deleted == False)  # noqa: E712
    role_filter = _owner_role_filter_for_admin(ReviewSession, owner_role)
    if role_filter is not None:
        q = q.filter(role_filter)
    if review_kind:
        q = q.filter(ReviewSession.review_kind == _review_session_normalize_kind(review_kind))
    if review_scope:
        q = q.filter(ReviewSession.review_scope == _review_session_normalize_scope(review_scope))
    if selection_mode:
        q = q.filter(ReviewSession.selection_mode == _review_session_normalize_selection_mode(selection_mode))
    if tag and tag.strip():
        q = q.filter(ReviewSession.tags_text.contains(tag.strip()))
    if is_favorite is not None:
        q = q.filter(ReviewSession.is_favorite == is_favorite)
    if min_star_rating is not None:
        q = q.filter(ReviewSession.star_rating >= min_star_rating)
    if max_star_rating is not None:
        q = q.filter(ReviewSession.star_rating <= max_star_rating)
    if sort_by not in {None, "updated_at", "star_rating"}:
        raise HTTPException(400, "sort_by must be one of: updated_at, star_rating")
    if sort_order not in {"asc", "desc"}:
        raise HTTPException(400, "sort_order must be one of: asc, desc")
    order_desc = sort_order != "asc"
    if sort_by == "updated_at":
        order_expr = ReviewSession.updated_at.desc() if order_desc else ReviewSession.updated_at.asc()
        q = q.order_by(order_expr, ReviewSession.id.desc())
    elif sort_by == "star_rating":
        order_expr = ReviewSession.star_rating.desc() if order_desc else ReviewSession.star_rating.asc()
        q = q.order_by(order_expr, ReviewSession.updated_at.desc(), ReviewSession.id.desc())
    else:
        q = q.order_by(ReviewSession.updated_at.desc(), ReviewSession.id.desc())
    rows = q.offset((page - 1) * size).limit(size).all()
    return _attach_review_session_fields(db, rows)


def create_review_session(payload: ReviewSessionCreate, db: Session = Depends(get_db)):
    row = _create_review_session_from_payload(
        db,
        payload.model_dump(exclude={"trade_links"}),
        [x.model_dump() for x in (payload.trade_links or [])],
    )
    return row


def create_review_session_from_selection(payload: ReviewSessionCreateFromSelection, db: Session = Depends(get_db)):
    selection_target = _review_session_normalize_selection_target(payload.selection_target)
    selection_mode = _review_session_normalize_selection_mode(payload.selection_mode)

    trade_ids: List[int] = []
    if selection_mode == "manual":
        trade_ids = [int(x) for x in payload.trade_ids if int(x) > 0]
    elif selection_mode == "filter_snapshot":
        if selection_target == "current_page":
            trade_ids = [int(x) for x in payload.trade_ids if int(x) > 0]
        else:
            trade_ids = _build_trade_ids_from_filter(db, payload.filter_params or {})
    else:
        trade_ids = [int(x) for x in payload.trade_ids if int(x) > 0]

    dedup_ids: List[int] = []
    seen = set()
    for tid in trade_ids:
        if tid in seen:
            continue
        seen.add(tid)
        dedup_ids.append(tid)

    trade_links = [{"trade_id": tid, "role": "linked_trade", "sort_order": idx} for idx, tid in enumerate(dedup_ids)]
    filter_snapshot = payload.filter_snapshot_json
    if not filter_snapshot and payload.filter_params is not None:
        filter_snapshot = json.dumps(
            {
                "selection_mode": selection_mode,
                "selection_target": selection_target,
                "filter_params": payload.filter_params,
            },
            ensure_ascii=False,
        )

    row = _create_review_session_from_payload(
        db,
        {
            "title": payload.title,
            "review_kind": payload.review_kind,
            "review_scope": payload.review_scope,
            "selection_mode": selection_mode,
            "selection_basis": payload.selection_basis,
            "review_goal": payload.review_goal,
            "market_regime": payload.market_regime,
            "summary": payload.summary,
            "repeated_errors": payload.repeated_errors,
            "next_focus": payload.next_focus,
            "action_items": payload.action_items,
            "tags": payload.tags,
            "filter_snapshot_json": filter_snapshot,
        },
        trade_links,
    )
    return row


def get_review_session(review_session_id: int, db: Session = Depends(get_db)):
    row = db.query(ReviewSession).filter(ReviewSession.id == review_session_id, ReviewSession.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Review session not found")
    return _attach_review_session_fields(db, [row])[0]


def update_review_session(review_session_id: int, data: ReviewSessionUpdate, db: Session = Depends(get_db)):
    row = db.query(ReviewSession).filter(ReviewSession.id == review_session_id, ReviewSession.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Review session not found")
    payload = data.model_dump(exclude_unset=True)
    tags_raw = payload.pop("tags", None) if "tags" in payload else None
    if "review_kind" in payload:
        payload["review_kind"] = _review_session_normalize_kind(payload.get("review_kind"))
    if "review_scope" in payload:
        payload["review_scope"] = _review_session_normalize_scope(payload.get("review_scope"))
    if "selection_mode" in payload:
        payload["selection_mode"] = _review_session_normalize_selection_mode(payload.get("selection_mode"))
    for k, v in payload.items():
        setattr(row, k, v)
    if tags_raw is not None:
        row.tags_text = _serialize_legacy_tags(_normalize_tag_list(tags_raw))
    db.commit()
    db.refresh(row)
    return _attach_review_session_fields(db, [row])[0]


def delete_review_session(review_session_id: int, db: Session = Depends(get_db)):
    row = db.query(ReviewSession).filter(ReviewSession.id == review_session_id, ReviewSession.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Review session not found")
    row.is_deleted = True
    row.deleted_at = datetime.now()
    db.commit()
    return {"ok": True}


def upsert_review_session_trade_links(
    review_session_id: int,
    payload: ReviewSessionTradeLinksPayload,
    db: Session = Depends(get_db),
):
    row = db.query(ReviewSession).filter(ReviewSession.id == review_session_id, ReviewSession.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Review session not found")
    _review_session_sync_trade_links(
        db,
        row,
        [x.model_dump() for x in (payload.trade_links or [])],
    )
    db.commit()
    db.refresh(row)
    return _attach_review_session_fields(db, [row])[0]


# Compatibility alias over canonical ReviewSession storage.
def list_reviews(
    review_type: Optional[str] = None,
    review_scope: Optional[str] = None,
    tag: Optional[str] = None,
    is_favorite: Optional[bool] = None,
    min_star_rating: Optional[int] = Query(None, ge=1, le=5),
    max_star_rating: Optional[int] = Query(None, ge=1, le=5),
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "desc",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    owner_role: Optional[str] = None,
    db: Session = Depends(get_db),
):
    kind_map = {
        "daily": "period",
        "weekly": "period",
        "monthly": "period",
        "custom": "custom",
    }
    kind = kind_map.get(review_type, None) if review_type else None
    rows = list_review_sessions(
        review_kind=kind,
        review_scope=review_scope,
        selection_mode=None,
        tag=tag,
        is_favorite=is_favorite,
        min_star_rating=min_star_rating,
        max_star_rating=max_star_rating,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        size=size,
        owner_role=owner_role,
        db=db,
    )
    if date_from or date_to:
        out_rows = []
        for row in rows:
            row_date = row.created_at.date() if row.created_at else date.today()
            if date_from and str(row_date) < str(date_from):
                continue
            if date_to and str(row_date) > str(date_to):
                continue
            out_rows.append(row)
        rows = out_rows
    return [_review_session_to_legacy_response(x) for x in rows]


def create_review(review: ReviewCreate, db: Session = Depends(get_db)):
    payload = review.model_dump()
    row = _create_review_session_from_payload(
        db,
        {
            "title": payload.get("title") or f"{payload.get('review_date')} {payload.get('review_type')}",
            "review_kind": "period" if payload.get("review_type") in {"daily", "weekly", "monthly"} else "custom",
            "review_scope": payload.get("review_scope"),
            "selection_mode": "manual",
            "selection_basis": payload.get("focus_topic") or payload.get("title") or "legacy-review",
            "review_goal": payload.get("summary") or payload.get("next_focus") or "legacy compatibility review",
            "market_regime": payload.get("market_regime"),
            "summary": payload.get("summary"),
            "repeated_errors": payload.get("repeated_errors"),
            "next_focus": payload.get("next_focus"),
            "action_items": payload.get("action_items"),
            "content": payload.get("content"),
            "research_notes": payload.get("research_notes"),
            "tags": payload.get("tags"),
            "is_favorite": payload.get("is_favorite"),
            "star_rating": payload.get("star_rating"),
            "filter_snapshot_json": None,
        },
        [],
    )
    return _review_session_to_legacy_response(row)


def get_review(review_id: int, db: Session = Depends(get_db)):
    row = db.query(ReviewSession).filter(ReviewSession.id == review_id, ReviewSession.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Review not found")
    row = _attach_review_session_fields(db, [row])[0]
    return _review_session_to_legacy_response(row)


def update_review(review_id: int, data: ReviewUpdate, db: Session = Depends(get_db)):
    row = db.query(ReviewSession).filter(ReviewSession.id == review_id, ReviewSession.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Review not found")
    payload = data.model_dump(exclude_unset=True)
    mapped = {
        "title": payload.get("title"),
        "review_scope": payload.get("review_scope"),
        "selection_basis": payload.get("focus_topic"),
        "review_goal": payload.get("summary") or payload.get("next_focus"),
        "market_regime": payload.get("market_regime"),
        "summary": payload.get("summary"),
        "repeated_errors": payload.get("repeated_errors"),
        "next_focus": payload.get("next_focus"),
        "action_items": payload.get("action_items"),
        "content": payload.get("content"),
        "research_notes": payload.get("research_notes"),
        "is_favorite": payload.get("is_favorite"),
        "star_rating": payload.get("star_rating"),
    }
    for k, v in mapped.items():
        if v is None:
            continue
        if k == "review_scope":
            setattr(row, k, _review_session_normalize_scope(v))
        else:
            setattr(row, k, v)
    if "tags" in payload:
        row.tags_text = _serialize_legacy_tags(_normalize_tag_list(payload.get("tags")))
    db.commit()
    db.refresh(row)
    row = _attach_review_session_fields(db, [row])[0]
    return _review_session_to_legacy_response(row)


def delete_review(review_id: int, db: Session = Depends(get_db)):
    row = db.query(ReviewSession).filter(ReviewSession.id == review_id, ReviewSession.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Review not found")
    row.is_deleted = True
    row.deleted_at = datetime.now()
    db.commit()
    return {"ok": True}


def upsert_review_trade_links(review_id: int, payload: ReviewTradeLinksPayload, db: Session = Depends(get_db)):
    row = db.query(ReviewSession).filter(ReviewSession.id == review_id, ReviewSession.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Review not found")
    _review_session_sync_trade_links(
        db,
        row,
        [{"trade_id": x.trade_id, "role": x.role, "note": x.notes} for x in (payload.trade_links or [])],
    )
    db.commit()
    db.refresh(row)
    row = _attach_review_session_fields(db, [row])[0]
    return _review_session_to_legacy_response(row)


# ── Trade Plan ──


def _attach_trade_plan_fields(db: Session, rows: List[TradePlan]) -> List[TradePlan]:
    rows = _trade_plan_attach_link_fields(db, rows)
    for row in rows:
        setattr(row, "tags", _parse_tags_text(row.tags_text))
    return rows


def list_trade_plans(
    status: Optional[str] = None,
    symbol: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    owner_role: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(TradePlan).filter(TradePlan.is_deleted == False)  # noqa: E712
    role_filter = _owner_role_filter_for_admin(TradePlan, owner_role)
    if role_filter is not None:
        q = q.filter(role_filter)
    if status:
        q = q.filter(TradePlan.status == _trade_plan_normalize_status(status))
    if symbol:
        q = q.filter(TradePlan.symbol == symbol)
    if date_from:
        q = q.filter(TradePlan.plan_date >= date_from)
    if date_to:
        q = q.filter(TradePlan.plan_date <= date_to)
    rows = q.order_by(TradePlan.updated_at.desc(), TradePlan.id.desc()).offset((page - 1) * size).limit(size).all()
    return _attach_trade_plan_fields(db, rows)


def create_trade_plan(payload: TradePlanCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude={"trade_links"})
    tags_raw = data.pop("tags", None) if "tags" in data else None
    data["status"] = _trade_plan_normalize_status(data.get("status"))
    obj = TradePlan(**data, owner_role=_owner_role_value_for_create())
    db.add(obj)
    db.flush()
    obj.tags_text = _serialize_legacy_tags(_normalize_tag_list(tags_raw))
    _trade_plan_sync_trade_links(db, obj, [x.model_dump() for x in (payload.trade_links or [])])
    db.commit()
    db.refresh(obj)
    return _attach_trade_plan_fields(db, [obj])[0]


def get_trade_plan(trade_plan_id: int, db: Session = Depends(get_db)):
    row = db.query(TradePlan).filter(TradePlan.id == trade_plan_id, TradePlan.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Trade plan not found")
    return _attach_trade_plan_fields(db, [row])[0]


def update_trade_plan(trade_plan_id: int, payload: TradePlanUpdate, db: Session = Depends(get_db)):
    row = db.query(TradePlan).filter(TradePlan.id == trade_plan_id, TradePlan.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Trade plan not found")
    updates = payload.model_dump(exclude_unset=True)
    tags_raw = updates.pop("tags", None) if "tags" in updates else None
    if "status" in updates:
        next_status = _trade_plan_normalize_status(updates.get("status"))
        _trade_plan_assert_status_transition(row.status, next_status)
        updates["status"] = next_status
    for k, v in updates.items():
        setattr(row, k, v)
    if tags_raw is not None:
        row.tags_text = _serialize_legacy_tags(_normalize_tag_list(tags_raw))
    db.commit()
    db.refresh(row)
    return _attach_trade_plan_fields(db, [row])[0]


def delete_trade_plan(trade_plan_id: int, db: Session = Depends(get_db)):
    row = db.query(TradePlan).filter(TradePlan.id == trade_plan_id, TradePlan.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Trade plan not found")
    row.is_deleted = True
    row.deleted_at = datetime.now()
    db.commit()
    return {"ok": True}


def upsert_trade_plan_trade_links(
    trade_plan_id: int,
    payload: TradePlanTradeLinksPayload,
    db: Session = Depends(get_db),
):
    row = db.query(TradePlan).filter(TradePlan.id == trade_plan_id, TradePlan.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Trade plan not found")
    _trade_plan_sync_trade_links(db, row, [x.model_dump() for x in (payload.trade_links or [])])
    db.commit()
    db.refresh(row)
    return _attach_trade_plan_fields(db, [row])[0]


def upsert_trade_plan_review_session_links(
    trade_plan_id: int,
    payload: TradePlanReviewSessionLinksPayload,
    db: Session = Depends(get_db),
):
    row = db.query(TradePlan).filter(TradePlan.id == trade_plan_id, TradePlan.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Trade plan not found")
    _trade_plan_sync_review_session_links(db, row, [x.model_dump() for x in (payload.review_session_links or [])])
    db.commit()
    db.refresh(row)
    return _attach_trade_plan_fields(db, [row])[0]


def create_followup_review_session_from_trade_plan(trade_plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(TradePlan).filter(TradePlan.id == trade_plan_id, TradePlan.is_deleted == False).first()  # noqa: E712
    if not plan:
        raise HTTPException(404, "Trade plan not found")
    plan = _attach_trade_plan_fields(db, [plan])[0]
    trade_links = [
        {"trade_id": x.trade_id, "role": "linked_trade", "sort_order": idx}
        for idx, x in enumerate(getattr(plan, "trade_links", []))
    ]
    session = _create_review_session_from_payload(
        db,
        {
            "title": f"计划跟踪复盘：{plan.title}",
            "review_kind": "plan-followup",
            "review_scope": "campaign",
            "selection_mode": "plan_linked",
            "selection_basis": f"来自交易计划 #{plan.id} 的关联成交样本",
            "review_goal": "评估计划到执行的转化质量与偏差",
            "market_regime": plan.market_regime,
            "summary": None,
            "repeated_errors": None,
            "next_focus": None,
            "action_items": None,
            "content": None,
            "research_notes": None,
            "tags": _parse_tags_text(plan.tags_text),
            "filter_snapshot_json": json.dumps({"source": "trade_plan", "trade_plan_id": plan.id}, ensure_ascii=False),
            "owner_role": plan.owner_role,
        },
        trade_links,
    )
    _trade_plan_sync_review_session_links(
        db,
        plan,
        [{"review_session_id": session.id, "note": "自动创建计划跟踪复盘"}],
    )
    db.commit()
    db.refresh(plan)
    return session


# ── Trading Recycle Bin ──


def list_recycle_trades(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Trade)
        .filter(Trade.is_deleted == True)  # noqa: E712
        .order_by(Trade.deleted_at.desc(), Trade.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return _attach_trade_view_fields(db, rows)


def restore_recycle_trade(trade_id: int, db: Session = Depends(get_db)):
    row = db.query(Trade).filter(Trade.id == trade_id, Trade.is_deleted == True).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Trade not found in recycle bin")
    row.is_deleted = False
    row.deleted_at = None
    db.commit()
    db.refresh(row)
    return _attach_trade_view_fields(db, [row])[0]


def purge_recycle_trade(trade_id: int, db: Session = Depends(get_db)):
    row = db.query(Trade).filter(Trade.id == trade_id, Trade.is_deleted == True).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Trade not found in recycle bin")
    db.query(ReviewSessionTradeLink).filter(ReviewSessionTradeLink.trade_id == trade_id).delete(synchronize_session=False)
    db.query(TradePlanTradeLink).filter(TradePlanTradeLink.trade_id == trade_id).delete(synchronize_session=False)
    db.query(ReviewTradeLink).filter(ReviewTradeLink.trade_id == trade_id).delete(synchronize_session=False)
    db.delete(row)
    db.commit()
    return {"ok": True}


def list_recycle_knowledge_items(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(KnowledgeItem)
        .filter(KnowledgeItem.is_deleted == True)  # noqa: E712
        .order_by(KnowledgeItem.deleted_at.desc(), KnowledgeItem.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    rows = _attach_knowledge_item_tags(db, rows)
    return _knowledge_attach_related_notes(db, rows)


def restore_recycle_knowledge_item(item_id: int, db: Session = Depends(get_db)):
    row = db.query(KnowledgeItem).filter(KnowledgeItem.id == item_id, KnowledgeItem.is_deleted == True).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Knowledge item not found in recycle bin")
    row.is_deleted = False
    row.deleted_at = None
    db.commit()
    db.refresh(row)
    rows = _attach_knowledge_item_tags(db, [row])
    rows = _knowledge_attach_related_notes(db, rows)
    return rows[0]


def purge_recycle_knowledge_item(item_id: int, db: Session = Depends(get_db)):
    row = db.query(KnowledgeItem).filter(KnowledgeItem.id == item_id, KnowledgeItem.is_deleted == True).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Knowledge item not found in recycle bin")
    db.delete(row)
    db.commit()
    return {"ok": True}


def list_recycle_trade_brokers(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return (
        db.query(TradeBroker)
        .filter(TradeBroker.is_deleted == True)  # noqa: E712
        .order_by(TradeBroker.deleted_at.desc(), TradeBroker.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )


def restore_recycle_trade_broker(broker_id: int, db: Session = Depends(get_db)):
    row = db.query(TradeBroker).filter(TradeBroker.id == broker_id, TradeBroker.is_deleted == True).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Trade broker not found in recycle bin")
    row.is_deleted = False
    row.deleted_at = None
    db.commit()
    db.refresh(row)
    return row


def purge_recycle_trade_broker(broker_id: int, db: Session = Depends(get_db)):
    row = db.query(TradeBroker).filter(TradeBroker.id == broker_id, TradeBroker.is_deleted == True).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Trade broker not found in recycle bin")
    db.delete(row)
    db.commit()
    return {"ok": True}


def list_recycle_review_sessions(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ReviewSession)
        .filter(ReviewSession.is_deleted == True)  # noqa: E712
        .order_by(ReviewSession.deleted_at.desc(), ReviewSession.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return _attach_review_session_fields(db, rows)


def restore_recycle_review_session(review_session_id: int, db: Session = Depends(get_db)):
    row = (
        db.query(ReviewSession)
        .filter(ReviewSession.id == review_session_id, ReviewSession.is_deleted == True)  # noqa: E712
        .first()
    )
    if not row:
        raise HTTPException(404, "Review session not found in recycle bin")
    row.is_deleted = False
    row.deleted_at = None
    db.commit()
    db.refresh(row)
    return _attach_review_session_fields(db, [row])[0]


def purge_recycle_review_session(review_session_id: int, db: Session = Depends(get_db)):
    row = (
        db.query(ReviewSession)
        .filter(ReviewSession.id == review_session_id, ReviewSession.is_deleted == True)  # noqa: E712
        .first()
    )
    if not row:
        raise HTTPException(404, "Review session not found in recycle bin")
    db.query(TradePlanReviewSessionLink).filter(
        TradePlanReviewSessionLink.review_session_id == review_session_id
    ).delete(synchronize_session=False)
    db.delete(row)
    db.commit()
    return {"ok": True}


def list_recycle_trade_plans(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(TradePlan)
        .filter(TradePlan.is_deleted == True)  # noqa: E712
        .order_by(TradePlan.deleted_at.desc(), TradePlan.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return _attach_trade_plan_fields(db, rows)


def restore_recycle_trade_plan(trade_plan_id: int, db: Session = Depends(get_db)):
    row = db.query(TradePlan).filter(TradePlan.id == trade_plan_id, TradePlan.is_deleted == True).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Trade plan not found in recycle bin")
    row.is_deleted = False
    row.deleted_at = None
    db.commit()
    db.refresh(row)
    return _attach_trade_plan_fields(db, [row])[0]


def purge_recycle_trade_plan(trade_plan_id: int, db: Session = Depends(get_db)):
    row = db.query(TradePlan).filter(TradePlan.id == trade_plan_id, TradePlan.is_deleted == True).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Trade plan not found in recycle bin")
    db.delete(row)
    db.commit()
    return {"ok": True}


# ── Notebook ──


def list_notebooks(owner_role: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Notebook)
    role_filter = _owner_role_filter_for_admin(Notebook, owner_role)
    if role_filter is not None:
        q = q.filter(role_filter)
    return q.order_by(Notebook.sort_order, Notebook.id).all()


def create_notebook(data: NotebookCreate, db: Session = Depends(get_db)):
    obj = Notebook(**data.model_dump(), owner_role=_owner_role_value_for_create())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_notebook(nb_id: int, data: NotebookUpdate, db: Session = Depends(get_db)):
    nb = db.query(Notebook).filter(Notebook.id == nb_id).first()
    if not nb:
        raise HTTPException(404, "Notebook not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(nb, k, v)
    db.commit()
    db.refresh(nb)
    return nb


def delete_notebook(nb_id: int, db: Session = Depends(get_db)):
    nb = db.query(Notebook).filter(Notebook.id == nb_id).first()
    if not nb:
        raise HTTPException(404, "Notebook not found")
    db.delete(nb)
    db.commit()
    return {"ok": True}


# ── Note ──


def list_notes(
    notebook_id: Optional[int] = None,
    note_type: Optional[str] = None,
    note_date: Optional[str] = None,
    keyword: Optional[str] = None,
    tag: Optional[str] = None,
    is_pinned: Optional[bool] = None,
    owner_role: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Note).filter(Note.is_deleted == False)  # noqa: E712
    role_filter = _owner_role_filter_for_admin(Note, owner_role)
    if role_filter is not None:
        q = q.filter(role_filter)
    if notebook_id:
        q = q.filter(Note.notebook_id == notebook_id)
    if note_type:
        q = q.filter(Note.note_type == note_type)
    if note_date:
        q = q.filter(Note.note_date == note_date)
    if keyword:
        q = q.filter(
            (Note.title.contains(keyword)) | (Note.content.contains(keyword))
        )
    if tag:
        q = q.filter(Note.tags.contains(tag))
    if is_pinned is not None:
        q = q.filter(Note.is_pinned == is_pinned)
    return (
        q.order_by(Note.is_pinned.desc(), Note.updated_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )


def note_stats(db: Session = Depends(get_db)):
    from sqlalchemy import func as sqlfunc
    diary_count = db.query(Note).filter(Note.note_type == "diary", Note.is_deleted == False).count()  # noqa: E712
    doc_count = db.query(Note).filter(Note.note_type == "doc", Note.is_deleted == False).count()  # noqa: E712
    diary_words = db.query(sqlfunc.coalesce(sqlfunc.sum(Note.word_count), 0)).filter(Note.note_type == "diary", Note.is_deleted == False).scalar()  # noqa: E712
    doc_words = db.query(sqlfunc.coalesce(sqlfunc.sum(Note.word_count), 0)).filter(Note.note_type == "doc", Note.is_deleted == False).scalar()  # noqa: E712
    recent_docs = (
        db.query(Note)
        .filter(Note.note_type == "doc", Note.is_deleted == False)  # noqa: E712
        .order_by(Note.updated_at.desc())
        .limit(8)
        .all()
    )
    return {
        "diary_count": diary_count,
        "doc_count": doc_count,
        "diary_word_count": diary_words,
        "doc_word_count": doc_words,
        "recent_docs": [
            {"id": n.id, "title": n.title or "无标题", "updated_at": str(n.updated_at)}
            for n in recent_docs
        ],
    }


def history_today(db: Session = Depends(get_db)):
    from datetime import date as dt_date
    from sqlalchemy import func as sqlfunc
    today = dt_date.today()
    md = today.strftime("%m-%d")
    notes = (
        db.query(Note)
        .filter(
            Note.note_type == "diary",
            Note.note_date.isnot(None),
            Note.is_deleted == False,  # noqa: E712
            sqlfunc.strftime("%m-%d", Note.note_date) == md,
            sqlfunc.strftime("%Y", Note.note_date) != str(today.year),
        )
        .order_by(Note.note_date.desc())
        .all()
    )
    return [
        {"id": n.id, "title": n.title, "note_date": str(n.note_date)}
        for n in notes
    ]


def diary_tree(db: Session = Depends(get_db)):
    from sqlalchemy import func as sqlfunc
    notes = (
        db.query(Note.id, Note.title, Note.note_date)
        .filter(Note.note_type == "diary", Note.note_date.isnot(None), Note.is_deleted == False)  # noqa: E712
        .order_by(Note.note_date.desc())
        .all()
    )
    tree = {}
    for n in notes:
        y = str(n.note_date.year) + "年"
        m = str(n.note_date.month) + "月"
        d = str(n.note_date.day).zfill(2) + "日"
        tree.setdefault(y, {}).setdefault(m, []).append(
            {"id": n.id, "title": n.title, "date": str(n.note_date), "day": d}
        )
    return tree


def _extract_tiptap_text(node) -> str:
    if isinstance(node, dict):
        parts = []
        txt = node.get("text")
        if isinstance(txt, str) and txt.strip():
            parts.append(txt.strip())
        content = node.get("content")
        if isinstance(content, list):
            for child in content:
                child_txt = _extract_tiptap_text(child)
                if child_txt:
                    parts.append(child_txt)
        return " ".join(parts).strip()
    if isinstance(node, list):
        return " ".join(filter(None, (_extract_tiptap_text(x) for x in node))).strip()
    return ""


def _note_summary_text(content: Optional[str], title: Optional[str]) -> str:
    fallback = (title or "").strip() or "（无内容）"
    if not content:
        return fallback
    raw = str(content).strip()
    if not raw:
        return fallback
    text_out = ""
    try:
        obj = json.loads(raw)
        text_out = _extract_tiptap_text(obj)
    except Exception:
        text_out = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    text_out = re.sub(r"\s+", " ", text_out).strip()
    if not text_out:
        return fallback
    return text_out[:120]


def _note_plain_text(content: Optional[str], title: Optional[str]) -> str:
    fallback = (title or "").strip()
    if not content:
        return fallback
    raw = str(content).strip()
    if not raw:
        return fallback
    try:
        obj = json.loads(raw)
        text_out = _extract_tiptap_text(obj)
    except Exception:
        text_out = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    text_out = re.sub(r"\s+", " ", text_out).strip()
    return text_out or fallback


def _make_search_snippet(text: str, keyword: str, width: int = 90) -> str:
    if not text:
        return ""
    key = (keyword or "").strip().lower()
    if not key:
        return text[:width]
    low = text.lower()
    idx = low.find(key)
    if idx < 0:
        return text[:width]
    start = max(0, idx - width // 2)
    end = min(len(text), idx + len(keyword) + width // 2)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def _split_keywords(q: str) -> List[str]:
    return [k for k in re.split(r"\s+", (q or "").strip().lower()) if k]


def _search_rank(title: str, plain: str, keys: List[str]) -> int:
    if not keys:
        return 0
    t = (title or "").lower()
    p = (plain or "").lower()
    score = 0
    for k in keys:
        if k in t:
            score += 8
        if k in p:
            score += 3
        if t.startswith(k):
            score += 2
    if all(k in t for k in keys):
        score += 6
    if all(k in p for k in keys):
        score += 2
    return score


def _parse_note_wikilinks(text: str) -> List[tuple[str, Optional[str]]]:
    out = []
    seen = set()
    for m in re.finditer(r"\[\[([^\[\]\n]{1,220})\]\]", text or ""):
        raw = (m.group(1) or "").strip()
        if not raw:
            continue
        name, heading = (raw.split("#", 1) + [None])[:2]
        name = (name or "").strip()
        heading = (heading or "").strip() or None
        if not name:
            continue
        key = (name.lower(), (heading or "").lower())
        if key in seen:
            continue
        seen.add(key)
        out.append((name, heading))
    return out


def _resolve_link_target_id(db: Session, target_name: str) -> Optional[int]:
    name = (target_name or "").strip()
    if not name:
        return None
    note = (
        db.query(Note)
        .filter(
            Note.title == name,
            Note.note_type == "doc",
            Note.is_deleted == False,  # noqa: E712
        )
        .order_by(Note.updated_at.desc())
        .first()
    )
    if note:
        return note.id
    note = (
        db.query(Note)
        .filter(
            Note.title == name,
            Note.is_deleted == False,  # noqa: E712
        )
        .order_by(Note.updated_at.desc())
        .first()
    )
    return note.id if note else None


def _index_note_links(db: Session, note: Note):
    db.query(NoteLink).filter(NoteLink.source_note_id == note.id).delete(synchronize_session=False)
    plain = _note_plain_text(note.content, note.title)
    for name, heading in _parse_note_wikilinks(plain):
        db.add(NoteLink(
            source_note_id=note.id,
            target_note_id=_resolve_link_target_id(db, name),
            target_name=name,
            target_heading=heading,
        ))


def _refresh_link_targets(db: Session):
    links = db.query(NoteLink).all()
    for lk in links:
        lk.target_note_id = _resolve_link_target_id(db, lk.target_name)


def _index_links_for_existing_notes():
    db = SessionLocal()
    try:
        notes = db.query(Note).filter(Note.is_deleted == False).all()  # noqa: E712
        db.query(NoteLink).delete(synchronize_session=False)
        for n in notes:
            _index_note_links(db, n)
        db.commit()
    finally:
        db.close()




def search_notes(
    q: str = Query(..., min_length=1),
    note_type: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    kw = q.strip()
    keys = _split_keywords(kw)
    if not keys:
        return []
    rows = (
        db.query(Note)
        .filter(Note.is_deleted == False)  # noqa: E712
        .order_by(Note.updated_at.desc())
        .limit(500)
        .all()
    )
    out = []
    for n in rows:
        if note_type and n.note_type != note_type:
            continue
        title = (n.title or "").strip()
        plain = _note_plain_text(n.content, title)
        t_low = title.lower()
        p_low = plain.lower()
        if not all((k in t_low) or (k in p_low) for k in keys):
            continue
        rank = _search_rank(title, plain, keys)
        out.append({
            "id": n.id,
            "title": title or "无标题",
            "note_type": n.note_type,
            "note_date": str(n.note_date) if n.note_date else None,
            "updated_at": str(n.updated_at) if n.updated_at else None,
            "snippet": _make_search_snippet(plain, keys[0]),
            "notebook_id": n.notebook_id,
            "_rank": rank,
            "_ts": n.updated_at.timestamp() if n.updated_at else 0,
        })
    out.sort(key=lambda x: (-x["_rank"], -x["_ts"], -x["id"]))
    trimmed = out[:limit]
    for item in trimmed:
        item.pop("_rank", None)
        item.pop("_ts", None)
    return trimmed


def resolve_note_link(
    name: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    target_name = name.strip()
    target_id = _resolve_link_target_id(db, target_name)
    if not target_id:
        return {"resolved": False, "matches": []}
    n = db.query(Note).filter(Note.id == target_id, Note.is_deleted == False).first()  # noqa: E712
    if not n:
        return {"resolved": False, "matches": []}
    return {
        "resolved": True,
        "matches": [{
            "id": n.id,
            "title": n.title,
            "note_type": n.note_type,
            "notebook_id": n.notebook_id,
            "updated_at": str(n.updated_at) if n.updated_at else None,
        }],
    }


def note_backlinks(note_id: int, limit: int = Query(100, ge=1, le=300), db: Session = Depends(get_db)):
    target = db.query(Note).filter(Note.id == note_id, Note.is_deleted == False).first()  # noqa: E712
    if not target:
        raise HTTPException(404, "Note not found")
    rows = (
        db.query(NoteLink, Note)
        .join(Note, Note.id == NoteLink.source_note_id)
        .filter(
            NoteLink.target_note_id == note_id,
            Note.is_deleted == False,  # noqa: E712
        )
        .order_by(Note.updated_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for lk, src in rows:
        plain = _note_plain_text(src.content, src.title)
        needle = f"[[{lk.target_name}]]"
        if lk.target_heading:
            needle = f"[[{lk.target_name}#{lk.target_heading}]]"
        out.append({
            "source_note_id": src.id,
            "source_title": src.title or "无标题",
            "source_note_type": src.note_type,
            "source_updated_at": str(src.updated_at) if src.updated_at else None,
            "snippet": _make_search_snippet(plain, needle),
            "target_name": lk.target_name,
            "target_heading": lk.target_heading,
        })
    return out


def diary_summaries(
    year: int = Query(..., ge=1970, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
):
    from sqlalchemy import extract
    q = db.query(Note).filter(Note.note_type == "diary", Note.note_date.isnot(None), Note.is_deleted == False)  # noqa: E712
    q = q.filter(extract("year", Note.note_date) == year)
    if month is not None:
        q = q.filter(extract("month", Note.note_date) == month)
    notes = q.order_by(Note.note_date.asc()).all()
    return [
        {
            "id": n.id,
            "note_date": str(n.note_date),
            "summary": _note_summary_text(n.content, n.title),
        }
        for n in notes
    ]


def notes_calendar(
    year: int = Query(...),
    month: int = Query(...),
    db: Session = Depends(get_db),
):
    from sqlalchemy import extract
    dates = (
        db.query(Note.note_date)
        .filter(
            Note.note_type == "diary",
            Note.note_date.isnot(None),
            Note.is_deleted == False,  # noqa: E712
            extract("year", Note.note_date) == year,
            extract("month", Note.note_date) == month,
        )
        .distinct()
        .all()
    )
    return [str(d[0]) for d in dates]


def create_note(data: NoteCreate, db: Session = Depends(get_db)):
    nb = db.query(Notebook).filter(Notebook.id == data.notebook_id).first()
    if not nb:
        raise HTTPException(404, "Notebook not found")
    obj = Note(**data.model_dump(), owner_role=nb.owner_role or _owner_role_value_for_create())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    _index_note_links(db, obj)
    _refresh_link_targets(db)
    db.commit()
    return obj


def get_note(note_id: int, db: Session = Depends(get_db)):
    n = db.query(Note).filter(Note.id == note_id, Note.is_deleted == False).first()  # noqa: E712
    if not n:
        raise HTTPException(404, "Note not found")
    return n


def update_note(note_id: int, data: NoteUpdate, db: Session = Depends(get_db)):
    n = db.query(Note).filter(Note.id == note_id, Note.is_deleted == False).first()  # noqa: E712
    if not n:
        raise HTTPException(404, "Note not found")
    old_title = (n.title or "").strip()
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(n, k, v)
    _index_note_links(db, n)
    if (n.title or "").strip() != old_title:
        _refresh_link_targets(db)
    db.commit()
    db.refresh(n)
    return n


def delete_note(note_id: int, db: Session = Depends(get_db)):
    n = db.query(Note).filter(Note.id == note_id, Note.is_deleted == False).first()  # noqa: E712
    if not n:
        raise HTTPException(404, "Note not found")
    n.is_deleted = True
    n.deleted_at = datetime.now()
    db.query(NoteLink).filter(NoteLink.source_note_id == note_id).delete(synchronize_session=False)
    db.query(NoteLink).filter(NoteLink.target_note_id == note_id).update(
        {NoteLink.target_note_id: None},
        synchronize_session=False,
    )
    db.commit()
    return {"ok": True}


def list_recycle_notes(
    note_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Note).filter(Note.is_deleted == True)  # noqa: E712
    if note_type:
        q = q.filter(Note.note_type == note_type)
    return q.order_by(Note.deleted_at.desc()).all()


def restore_note(note_id: int, db: Session = Depends(get_db)):
    n = db.query(Note).filter(Note.id == note_id, Note.is_deleted == True).first()  # noqa: E712
    if not n:
        raise HTTPException(404, "Note not found in recycle bin")
    n.is_deleted = False
    n.deleted_at = None
    _index_note_links(db, n)
    _refresh_link_targets(db)
    db.commit()
    db.refresh(n)
    return n


def purge_note(note_id: int, db: Session = Depends(get_db)):
    n = db.query(Note).filter(Note.id == note_id).first()
    if not n:
        raise HTTPException(404, "Note not found")
    db.query(NoteLink).filter(NoteLink.source_note_id == note_id).delete(synchronize_session=False)
    db.query(NoteLink).filter(NoteLink.target_note_id == note_id).delete(synchronize_session=False)
    db.delete(n)
    db.commit()
    return {"ok": True}


def clear_recycle_notes(
    note_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Note).filter(Note.is_deleted == True)  # noqa: E712
    if note_type:
        q = q.filter(Note.note_type == note_type)
    rows = q.all()
    if not rows:
        return {"ok": True, "deleted": 0}
    ids = [n.id for n in rows]
    db.query(NoteLink).filter(NoteLink.source_note_id.in_(ids)).delete(synchronize_session=False)
    db.query(NoteLink).filter(NoteLink.target_note_id.in_(ids)).delete(synchronize_session=False)
    db.query(Note).filter(Note.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "deleted": len(ids)}


def list_todos(
    include_completed: bool = Query(True),
    keyword: Optional[str] = Query(None),
    owner_role: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(TodoItem)
    role_filter = _owner_role_filter_for_admin(TodoItem, owner_role)
    if role_filter is not None:
        q = q.filter(role_filter)
    if not include_completed:
        q = q.filter(TodoItem.is_completed == False)  # noqa: E712
    if keyword and keyword.strip():
        q = q.filter(TodoItem.content.contains(keyword.strip()))
    items = q.order_by(TodoItem.is_completed.asc(), TodoItem.created_at.desc()).all()
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda x: (
        1 if x.is_completed else 0,
        0 if x.due_at else 1,
        x.due_at.timestamp() if x.due_at else 0,
        priority_rank.get(x.priority, 1),
        -(x.created_at.timestamp() if x.created_at else 0),
    ))
    return items


def create_todo(data: TodoCreate, db: Session = Depends(get_db)):
    content = (data.content or "").strip()
    if not content:
        raise HTTPException(400, "待办内容不能为空")
    priority = _normalize_todo_priority(data.priority)
    src = None
    if data.source_note_id is not None:
        src = db.query(Note).filter(Note.id == data.source_note_id).first()
        if not src:
            raise HTTPException(404, "source_note_id 对应日记不存在")
    if data.due_at and data.reminder_at and data.reminder_at > data.due_at:
        raise HTTPException(400, "提醒时间不能晚于截止时间")
    obj = TodoItem(
        content=content,
        priority=priority,
        is_completed=False,
        source_note_id=data.source_note_id,
        source_anchor_text=(data.source_anchor_text or "").strip() or None,
        due_at=data.due_at,
        reminder_at=data.reminder_at,
        owner_role=(src.owner_role if src else _owner_role_value_for_create()),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_todo(todo_id: int, data: TodoUpdate, db: Session = Depends(get_db)):
    obj = db.query(TodoItem).filter(TodoItem.id == todo_id).first()
    if not obj:
        raise HTTPException(404, "Todo not found")
    updates = data.model_dump(exclude_unset=True)
    if "content" in updates:
        updates["content"] = (updates["content"] or "").strip()
        if not updates["content"]:
            raise HTTPException(400, "待办内容不能为空")
    if "priority" in updates:
        updates["priority"] = _normalize_todo_priority(updates["priority"])
    if "source_anchor_text" in updates:
        updates["source_anchor_text"] = (updates["source_anchor_text"] or "").strip() or None
    due_at = updates.get("due_at", obj.due_at)
    reminder_at = updates.get("reminder_at", obj.reminder_at)
    if due_at and reminder_at and reminder_at > due_at:
        raise HTTPException(400, "提醒时间不能晚于截止时间")
    for k, v in updates.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    obj = db.query(TodoItem).filter(TodoItem.id == todo_id).first()
    if not obj:
        raise HTTPException(404, "Todo not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}


def _build_poem_payload(entry: dict, source: str) -> dict:
    title = (entry.get("title") or "").strip() or "无题"
    author = (entry.get("author") or "").strip() or "佚名"
    text_val = (entry.get("text") or "").strip()
    if not text_val:
        raise ValueError("poem text empty")
    return {
        "title": title,
        "author": author,
        "text": text_val,
        "source": source,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


def _fetch_remote_poem() -> dict:
    headers = {"User-Agent": "Mozilla/5.0"}
    if JINRISHICI_TOKEN:
        headers["X-User-Token"] = JINRISHICI_TOKEN
    with httpx.Client(timeout=8) as client:
        resp = client.get(POEM_REMOTE_URL, headers=headers)
    resp.raise_for_status()
    raw = resp.json()
    data = raw.get("data") if isinstance(raw, dict) else {}
    origin = data.get("origin") if isinstance(data, dict) else {}
    lines = origin.get("content") if isinstance(origin, dict) else None
    if isinstance(lines, list):
        text_val = "\n".join(str(x).strip() for x in lines if str(x).strip()).strip()
    else:
        text_val = (data.get("content") or "").strip()
    return _build_poem_payload(
        {
            "title": origin.get("title") if isinstance(origin, dict) else None,
            "author": origin.get("author") if isinstance(origin, dict) else None,
            "text": text_val,
        },
        "今日诗词",
    )


def _fallback_poem(refresh: bool = False, exclude_title: Optional[str] = None) -> dict:
    candidates = POEM_FALLBACKS
    if refresh and exclude_title:
        filtered = [p for p in POEM_FALLBACKS if (p.get("title") or "").strip() != exclude_title]
        if filtered:
            candidates = filtered
    if refresh:
        pick = random.choice(candidates)
    else:
        idx = int(datetime.now().strftime("%j")) % len(candidates)
        pick = candidates[idx]
    return _build_poem_payload(pick, "本地兜底")


def get_daily_poem(refresh: bool = Query(False)):
    now_ts = _time.time()
    previous_title = None
    if not refresh:
        with _poem_lock:
            updated_at = _poem_cache["updated_at"]
            payload = _poem_cache["payload"]
            if payload and updated_at and (now_ts - updated_at) < POEM_CACHE_TTL:
                return payload
    else:
        with _poem_lock:
            old_payload = _poem_cache.get("payload") or {}
            previous_title = (old_payload.get("title") or "").strip() or None
    try:
        payload = _fetch_remote_poem()
    except Exception:
        payload = _fallback_poem(refresh=refresh, exclude_title=previous_title)
    with _poem_lock:
        _poem_cache["updated_at"] = now_ts
        _poem_cache["payload"] = payload
    return payload



# ── Poem ──

_poem_lock = threading.Lock()
_poem_cache = {"updated_at": None, "payload": None}
POEM_CACHE_TTL = int(os.environ.get("POEM_CACHE_TTL", "1800"))
POEM_REMOTE_URL = os.environ.get("POEM_REMOTE_URL", "https://v2.jinrishici.com/sentence")
JINRISHICI_TOKEN = os.environ.get("JINRISHICI_TOKEN", "").strip()
POEM_FALLBACKS = [
    {
        "title": "望岳",
        "author": "杜甫",
        "text": "岱宗夫如何？齐鲁青未了。\n造化钟神秀，阴阳割昏晓。\n荡胸生曾云，决眦入归鸟。\n会当凌绝顶，一览众山小。",
    },
    {
        "title": "水调歌头",
        "author": "苏轼",
        "text": "明月几时有？把酒问青天。\n不知天上宫阙，今夕是何年。\n我欲乘风归去，又恐琼楼玉宇，高处不胜寒。\n起舞弄清影，何似在人间。\n转朱阁，低绮户，照无眠。\n不应有恨，何事长向别时圆？\n人有悲欢离合，月有阴晴圆缺，此事古难全。\n但愿人长久，千里共婵娟。",
    },
    {
        "title": "沁园春·雪",
        "author": "毛泽东",
        "text": "北国风光，千里冰封，万里雪飘。\n望长城内外，惟余莽莽；大河上下，顿失滔滔。\n山舞银蛇，原驰蜡象，欲与天公试比高。\n须晴日，看红装素裹，分外妖娆。\n江山如此多娇，引无数英雄竞折腰。\n惜秦皇汉武，略输文采；唐宗宋祖，稍逊风骚。\n一代天骄，成吉思汗，只识弯弓射大雕。\n俱往矣，数风流人物，还看今朝。",
    },
]


# ══════════════════════════════════════════
#  Server Monitor
# ══════════════════════════════════════════

_monitor_history: deque = deque(maxlen=720)
_prev_net = psutil.net_io_counters()
_prev_disk_io = psutil.disk_io_counters()
_prev_ts = _time.time()
_net_speed = {"up": 0.0, "down": 0.0}
_disk_speed = {"read": 0.0, "write": 0.0}


def _bytes_fmt(b):
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} PB"


def _seconds_fmt(s):
    d, s = divmod(int(s), 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    parts = []
    if d:
        parts.append(f"{d}天")
    if h:
        parts.append(f"{h}小时")
    if m:
        parts.append(f"{m}分钟")
    parts.append(f"{s}秒")
    return " ".join(parts)


def _sample():
    global _prev_net, _prev_disk_io, _prev_ts, _net_speed, _disk_speed
    now = _time.time()
    dt = now - _prev_ts
    if dt <= 0:
        dt = 1

    net = psutil.net_io_counters()
    _net_speed = {
        "up": (net.bytes_sent - _prev_net.bytes_sent) / dt,
        "down": (net.bytes_recv - _prev_net.bytes_recv) / dt,
    }
    _prev_net = net

    try:
        dio = psutil.disk_io_counters()
        if dio:
            _disk_speed = {
                "read": (dio.read_bytes - _prev_disk_io.read_bytes) / dt,
                "write": (dio.write_bytes - _prev_disk_io.write_bytes) / dt,
            }
            _prev_disk_io = dio
    except Exception:
        pass

    _prev_ts = now

    cpu_pct = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    _monitor_history.append({
        "ts": datetime.now().strftime("%H:%M:%S"),
        "cpu": cpu_pct,
        "mem": mem.percent,
        "net_up": round(_net_speed["up"] / 1024, 1),
        "net_down": round(_net_speed["down"] / 1024, 1),
    })


def _monitor_loop():
    psutil.cpu_percent(interval=None)
    while True:
        try:
            _sample()
        except Exception:
            pass
        _time.sleep(5)


_monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)


BROWSE_LOG_RETENTION_DAYS = 180


def _cleanup_old_browse_logs():
    db = SessionLocal()
    try:
        cutoff = datetime.now() - timedelta(days=BROWSE_LOG_RETENTION_DAYS)
        db.query(BrowseLog).filter(BrowseLog.created_at < cutoff).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _maintenance_loop():
    while True:
        try:
            _cleanup_old_browse_logs()
        except Exception:
            pass
        _time.sleep(3600)


def _check_single_site(site: MonitorSite) -> Dict[str, Any]:
    started = _time.time()
    timeout_sec = max(2, min(60, int(site.timeout_sec or 8)))
    try:
        with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
            resp = client.get(site.url)
            elapsed_ms = int((_time.time() - started) * 1000)
            ok = 200 <= int(resp.status_code) < 400
            return {
                "status_code": int(resp.status_code),
                "response_ms": elapsed_ms,
                "ok": ok,
                "error": None if ok else f"http {resp.status_code}",
            }
    except Exception as exc:
        elapsed_ms = int((_time.time() - started) * 1000)
        return {"status_code": None, "response_ms": elapsed_ms, "ok": False, "error": str(exc)[:500]}


def _site_monitor_loop():
    while True:
        db = SessionLocal()
        try:
            now = datetime.now()
            rows = db.query(MonitorSite).filter(MonitorSite.enabled == True).all()  # noqa: E712
            for site in rows:
                interval_sec = max(10, min(3600, int(site.interval_sec or 60)))
                if site.last_checked_at and (now - site.last_checked_at).total_seconds() < interval_sec:
                    continue
                result = _check_single_site(site)
                site.last_checked_at = now
                site.last_status_code = result["status_code"]
                site.last_response_ms = result["response_ms"]
                site.last_ok = bool(result["ok"])
                site.last_error = result["error"]
                db.add(
                    MonitorSiteResult(
                        site_id=site.id,
                        status_code=result["status_code"],
                        response_ms=result["response_ms"],
                        ok=bool(result["ok"]),
                        error=result["error"],
                    )
                )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        _time.sleep(5)


_maintenance_thread = threading.Thread(target=_maintenance_loop, daemon=True)

_site_monitor_thread = threading.Thread(target=_site_monitor_loop, daemon=True)



_RUNTIME_INITIALIZED = False


def init_runtime() -> None:
    global _RUNTIME_INITIALIZED
    if _RUNTIME_INITIALIZED:
        return
    Base.metadata.create_all(bind=engine)
    _migrate_legacy_schema()
    _migrate_reviews_to_review_sessions()
    _init_default_notebooks()
    _migrate_legacy_auth_to_users()
    _index_links_for_existing_notes()
    _monitor_thread.start()
    _maintenance_thread.start()
    _site_monitor_thread.start()
    _RUNTIME_INITIALIZED = True


def _get_system_info():
    import platform
    boot = psutil.boot_time()
    uptime = _time.time() - boot
    hostname = platform.node()
    kernel = platform.release()
    arch = platform.machine()
    try:
        with open("/etc/os-release") as f:
            lines = f.readlines()
        distro = dict(l.strip().split("=", 1) for l in lines if "=" in l)
        os_name = distro.get("PRETTY_NAME", "").strip('"')
    except Exception:
        os_name = f"{platform.system()} {platform.version()}"
    return {
        "hostname": hostname,
        "os": os_name,
        "kernel": kernel,
        "arch": arch,
        "uptime": _seconds_fmt(uptime),
        "uptime_seconds": int(uptime),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _get_cpu_info():
    freq = psutil.cpu_freq()
    try:
        load = os.getloadavg()
        load_1, load_5, load_15 = round(load[0], 2), round(load[1], 2), round(load[2], 2)
    except (AttributeError, OSError):
        load_1 = load_5 = load_15 = 0.0
    temps = {}
    try:
        t = psutil.sensors_temperatures()
        if t:
            for name, entries in t.items():
                for e in entries:
                    if e.current > 0:
                        temps[e.label or name] = round(e.current, 1)
    except (AttributeError, Exception):
        pass
    return {
        "percent": psutil.cpu_percent(interval=None),
        "per_cpu": psutil.cpu_percent(interval=None, percpu=True),
        "cores_physical": psutil.cpu_count(logical=False),
        "cores_logical": psutil.cpu_count(logical=True),
        "freq_current": round(freq.current, 0) if freq else None,
        "freq_max": round(freq.max, 0) if freq and freq.max else None,
        "load_1": load_1,
        "load_5": load_5,
        "load_15": load_15,
        "temps": temps,
    }


def _get_memory_info():
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    return {
        "total": vm.total,
        "used": vm.used,
        "available": vm.available,
        "percent": vm.percent,
        "total_fmt": _bytes_fmt(vm.total),
        "used_fmt": _bytes_fmt(vm.used),
        "available_fmt": _bytes_fmt(vm.available),
        "swap_total": sw.total,
        "swap_used": sw.used,
        "swap_percent": sw.percent,
        "swap_total_fmt": _bytes_fmt(sw.total),
        "swap_used_fmt": _bytes_fmt(sw.used),
    }


def _get_disk_info():
    partitions = []
    for p in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(p.mountpoint)
            partitions.append({
                "device": p.device,
                "mountpoint": p.mountpoint,
                "fstype": p.fstype,
                "total": u.total,
                "used": u.used,
                "free": u.free,
                "percent": u.percent,
                "total_fmt": _bytes_fmt(u.total),
                "used_fmt": _bytes_fmt(u.used),
                "free_fmt": _bytes_fmt(u.free),
            })
        except Exception:
            pass
    return {
        "partitions": partitions,
        "io_read_speed": round(_disk_speed["read"] / 1024 / 1024, 2),
        "io_write_speed": round(_disk_speed["write"] / 1024 / 1024, 2),
    }


def _get_network_info():
    net = psutil.net_io_counters()
    return {
        "bytes_sent": net.bytes_sent,
        "bytes_recv": net.bytes_recv,
        "bytes_sent_fmt": _bytes_fmt(net.bytes_sent),
        "bytes_recv_fmt": _bytes_fmt(net.bytes_recv),
        "speed_up": round(_net_speed["up"] / 1024, 1),
        "speed_down": round(_net_speed["down"] / 1024, 1),
        "speed_up_fmt": _bytes_fmt(_net_speed["up"]) + "/s",
        "speed_down_fmt": _bytes_fmt(_net_speed["down"]) + "/s",
    }


def _get_top_processes(n=10):
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "username"]):
        try:
            info = p.info
            procs.append({
                "pid": info["pid"],
                "name": info["name"],
                "cpu": round(info["cpu_percent"] or 0, 1),
                "mem": round(info["memory_percent"] or 0, 1),
                "user": info["username"] or "",
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x["cpu"], reverse=True)
    return procs[:n]


def _get_services_status():
    targets = ["nginx", "uvicorn", "python"]
    result = {}
    all_names = set()
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            all_names.add(p.info["name"].lower())
            cmdline = " ".join(p.info["cmdline"] or []).lower()
            for svc in targets:
                if svc in p.info["name"].lower() or svc in cmdline:
                    result[svc] = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    for svc in targets:
        if svc not in result:
            result[svc] = False
    return result


def monitor_realtime():
    _require_admin()
    return {
        "system": _get_system_info(),
        "cpu": _get_cpu_info(),
        "memory": _get_memory_info(),
        "disk": _get_disk_info(),
        "network": _get_network_info(),
        "processes": _get_top_processes(),
        "services": _get_services_status(),
    }


def monitor_history():
    _require_admin()
    return list(_monitor_history)


def monitor_sites(db: Session = Depends(get_db)):
    _require_admin()
    rows = db.query(MonitorSite).order_by(MonitorSite.updated_at.desc(), MonitorSite.id.desc()).all()
    return [
        {
            "id": x.id,
            "name": x.name,
            "url": x.url,
            "enabled": bool(x.enabled),
            "interval_sec": x.interval_sec,
            "timeout_sec": x.timeout_sec,
            "last_checked_at": x.last_checked_at,
            "last_status_code": x.last_status_code,
            "last_response_ms": x.last_response_ms,
            "last_ok": x.last_ok,
            "last_error": x.last_error,
            "created_at": x.created_at,
            "updated_at": x.updated_at,
        }
        for x in rows
    ]


def create_monitor_site(payload: MonitorSiteCreateBody, request: Request, db: Session = Depends(get_db)):
    _require_admin()
    name = (payload.name or "").strip()
    url = (payload.url or "").strip()
    if not name:
        raise HTTPException(400, "name 不能为空")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "url 必须以 http:// 或 https:// 开头")
    row = MonitorSite(
        name=name,
        url=url,
        enabled=bool(payload.enabled),
        interval_sec=max(10, min(3600, int(payload.interval_sec or 60))),
        timeout_sec=max(2, min(60, int(payload.timeout_sec or 8))),
    )
    db.add(row)
    _write_browse_log(
        db,
        username=_current_username(),
        role=_current_role(),
        event_type="action",
        path="/api/monitor/sites",
        module="monitor_site",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail=f"create site {name}",
    )
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": row.id}


def update_monitor_site(site_id: int, payload: MonitorSiteUpdateBody, request: Request, db: Session = Depends(get_db)):
    _require_admin()
    row = db.query(MonitorSite).filter(MonitorSite.id == site_id).first()
    if not row:
        raise HTTPException(404, "site not found")
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        row.name = (updates.get("name") or "").strip() or row.name
    if "url" in updates:
        url = (updates.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            raise HTTPException(400, "url 必须以 http:// 或 https:// 开头")
        row.url = url
    if "enabled" in updates:
        row.enabled = bool(updates.get("enabled"))
    if "interval_sec" in updates and updates.get("interval_sec") is not None:
        row.interval_sec = max(10, min(3600, int(updates.get("interval_sec"))))
    if "timeout_sec" in updates and updates.get("timeout_sec") is not None:
        row.timeout_sec = max(2, min(60, int(updates.get("timeout_sec"))))
    _write_browse_log(
        db,
        username=_current_username(),
        role=_current_role(),
        event_type="action",
        path=f"/api/monitor/sites/{site_id}",
        module="monitor_site",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail=f"update site {row.name}",
    )
    db.commit()
    return {"ok": True}


def delete_monitor_site(site_id: int, request: Request, db: Session = Depends(get_db)):
    _require_admin()
    row = db.query(MonitorSite).filter(MonitorSite.id == site_id).first()
    if not row:
        raise HTTPException(404, "site not found")
    db.query(MonitorSiteResult).filter(MonitorSiteResult.site_id == site_id).delete(synchronize_session=False)
    db.delete(row)
    _write_browse_log(
        db,
        username=_current_username(),
        role=_current_role(),
        event_type="action",
        path=f"/api/monitor/sites/{site_id}",
        module="monitor_site",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail=f"delete site {site_id}",
    )
    db.commit()
    return {"ok": True}


def monitor_site_results(site_id: int, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    _require_admin()
    rows = (
        db.query(MonitorSiteResult)
        .filter(MonitorSiteResult.site_id == site_id)
        .order_by(MonitorSiteResult.created_at.desc(), MonitorSiteResult.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": x.id,
            "site_id": x.site_id,
            "status_code": x.status_code,
            "response_ms": x.response_ms,
            "ok": bool(x.ok),
            "error": x.error,
            "created_at": x.created_at,
        }
        for x in rows
    ]
