from fastapi import Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, func, or_, event
from sqlalchemy.orm import with_loader_criteria
from typing import Optional, List, Dict, Any
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
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from ebooklib import epub, ITEM_DOCUMENT

from core import context
from core.security import ensure_admin, normalize_owner_role

from core.db import engine, get_db, Base, SessionLocal
from models import (
    Trade, TradeReview, TradeSourceMetadata, Review, ReviewTradeLink, ReviewSession, ReviewSessionTradeLink,
    TradePlan, TradePlanTradeLink, TradePlanReviewSessionLink, KnowledgeCategory, KnowledgeItem,
    Notebook, Note, NoteLink, TodoItem, TradeBroker, BrowseLog,
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
    create_knowledge_category as _knowledge_create_category,
    delete_knowledge_category as _knowledge_delete_category,
    normalize_knowledge_category_name as _knowledge_normalize_category_name,
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
    KnowledgeCategory,
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


def _rebuild_ledger_schema_if_incompatible(db: Session) -> bool:
    # Breaking-change migration for ledger module:
    # if legacy tables conflict with new schema (e.g. missing ledger_rules.rule_type),
    # rebuild ledger tables because module is not yet in production.
    if not _table_exists(db, "ledger_rules"):
        return False

    rule_cols = _column_names(db, "ledger_rules")
    required_rule_cols = {
        "rule_type",
        "priority",
        "enabled",
        "match_mode",
        "pattern",
        "target_txn_kind",
        "target_scene",
    }
    if required_rule_cols.issubset(rule_cols):
        return False

    db.execute(text("PRAGMA foreign_keys = OFF"))
    for table in (
        "ledger_transactions",
        "ledger_import_rows",
        "ledger_import_batches",
        "ledger_rules",
        "ledger_merchants",
        "ledger_categories",
    ):
        if _table_exists(db, table):
            db.execute(text(f"DROP TABLE IF EXISTS {table}"))
    db.commit()
    db.execute(text("PRAGMA foreign_keys = ON"))
    Base.metadata.create_all(bind=engine)
    return True


def _migrate_legacy_schema():
    db = SessionLocal()
    try:
        _rebuild_ledger_schema_if_incompatible(db)
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
            _ensure_sqlite_column(db, "users", "module_permissions", "TEXT")
            _ensure_sqlite_column(db, "users", "data_permissions", "TEXT")
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
            _ensure_sqlite_column(db, "knowledge_items", "sub_category", "VARCHAR(100)")
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
        if _table_exists(db, "ledger_transactions"):
            _ensure_sqlite_column(db, "ledger_transactions", "confidence_score", "FLOAT")
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
    from services.notes_runtime import init_default_notebooks

    init_default_notebooks()


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


from services import notes_runtime as _notes_runtime

list_notebooks = _notes_runtime.list_notebooks
create_notebook = _notes_runtime.create_notebook
update_notebook = _notes_runtime.update_notebook
delete_notebook = _notes_runtime.delete_notebook
list_notes = _notes_runtime.list_notes
note_stats = _notes_runtime.note_stats
history_today = _notes_runtime.history_today
diary_tree = _notes_runtime.diary_tree
search_notes = _notes_runtime.search_notes
resolve_note_link = _notes_runtime.resolve_note_link
note_backlinks = _notes_runtime.note_backlinks
diary_summaries = _notes_runtime.diary_summaries
notes_calendar = _notes_runtime.notes_calendar
create_note = _notes_runtime.create_note
get_note = _notes_runtime.get_note
update_note = _notes_runtime.update_note
delete_note = _notes_runtime.delete_note
list_todos = _notes_runtime.list_todos
create_todo = _notes_runtime.create_todo
update_todo = _notes_runtime.update_todo
delete_todo = _notes_runtime.delete_todo


def _index_links_for_existing_notes():
    _notes_runtime.index_links_for_existing_notes()


from services import knowledge_runtime as _knowledge_runtime
from services import review_runtime as _review_runtime
from services import trade_plan_runtime as _trade_plan_runtime
from services import utility_runtime as _utility_runtime

list_knowledge_items = _knowledge_runtime.list_knowledge_items
list_knowledge_item_categories = _knowledge_runtime.list_knowledge_item_categories
create_knowledge_item_category = _knowledge_runtime.create_knowledge_item_category
delete_knowledge_item_category = _knowledge_runtime.delete_knowledge_item_category
create_knowledge_item = _knowledge_runtime.create_knowledge_item
get_knowledge_item = _knowledge_runtime.get_knowledge_item
update_knowledge_item = _knowledge_runtime.update_knowledge_item
delete_knowledge_item = _knowledge_runtime.delete_knowledge_item

_attach_review_session_fields = _review_runtime._attach_review_session_fields
list_review_sessions = _review_runtime.list_review_sessions
create_review_session = _review_runtime.create_review_session
create_review_session_from_selection = _review_runtime.create_review_session_from_selection
get_review_session = _review_runtime.get_review_session
update_review_session = _review_runtime.update_review_session
delete_review_session = _review_runtime.delete_review_session
upsert_review_session_trade_links = _review_runtime.upsert_review_session_trade_links
list_reviews = _review_runtime.list_reviews
create_review = _review_runtime.create_review
get_review = _review_runtime.get_review
update_review = _review_runtime.update_review
delete_review = _review_runtime.delete_review
upsert_review_trade_links = _review_runtime.upsert_review_trade_links

_attach_trade_plan_fields = _trade_plan_runtime._attach_trade_plan_fields
list_trade_plans = _trade_plan_runtime.list_trade_plans
create_trade_plan = _trade_plan_runtime.create_trade_plan
get_trade_plan = _trade_plan_runtime.get_trade_plan
update_trade_plan = _trade_plan_runtime.update_trade_plan
delete_trade_plan = _trade_plan_runtime.delete_trade_plan
upsert_trade_plan_trade_links = _trade_plan_runtime.upsert_trade_plan_trade_links
upsert_trade_plan_review_session_links = _trade_plan_runtime.upsert_trade_plan_review_session_links
create_followup_review_session_from_trade_plan = _trade_plan_runtime.create_followup_review_session_from_trade_plan

upload_file = _utility_runtime.upload_file
get_upload = _utility_runtime.get_upload
get_daily_poem = _utility_runtime.get_daily_poem


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


_maintenance_thread = threading.Thread(target=_maintenance_loop, daemon=True)



_RUNTIME_INITIALIZED = False


def init_runtime() -> None:
    global _RUNTIME_INITIALIZED
    if _RUNTIME_INITIALIZED:
        return
    from services.auth_runtime import migrate_legacy_auth_to_users
    Base.metadata.create_all(bind=engine)
    _migrate_legacy_schema()
    _migrate_reviews_to_review_sessions()
    _init_default_notebooks()
    migrate_legacy_auth_to_users()
    _index_links_for_existing_notes()
    _maintenance_thread.start()
    from services.monitor_runtime import init_monitor_runtime

    init_monitor_runtime()
    _RUNTIME_INITIALIZED = True
