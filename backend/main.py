from fastapi import FastAPI, Depends, HTTPException, Query, Request, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text, func, or_
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
from datetime import datetime, date, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
import psutil
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup

DEV_MODE = os.environ.get("DEV_MODE", "0") == "1"

from database import engine, get_db, Base, SessionLocal
from models import Trade, TradeReview, TradeSourceMetadata, Review, Notebook, Note, NoteLink, TodoItem, NewsIssue, TradeBroker
from schemas import (
    TradeCreate, TradeUpdate, TradeResponse,
    TradePasteImportRequest, TradePasteImportResponse, TradePasteImportError, TradePositionResponse,
    TradeReviewUpsert, TradeReviewResponse, TradeReviewTaxonomyResponse,
    TradeSourceMetadataUpsert, TradeSourceMetadataResponse,
    TradeBrokerCreate, TradeBrokerUpdate, TradeBrokerResponse,
    ReviewCreate, ReviewUpdate, ReviewResponse,
    NotebookCreate, NotebookUpdate, NotebookResponse,
    NoteCreate, NoteUpdate, NoteResponse,
    TodoCreate, TodoUpdate, TodoResponse,
    NewsIssueResponse, NewsIssueDetailResponse,
)
from auth import load_credentials, save_credentials, check_login, create_token, verify_token
from trade_review_taxonomy import trade_review_taxonomy

Base.metadata.create_all(bind=engine)


def _column_names(db: Session, table: str) -> set[str]:
    rows = db.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def _migrate_legacy_schema():
    db = SessionLocal()
    try:
        notebook_cols = _column_names(db, "notebooks")
        if "parent_id" not in notebook_cols:
            db.execute(text("ALTER TABLE notebooks ADD COLUMN parent_id INTEGER"))
        if "sort_order" not in notebook_cols:
            db.execute(text("ALTER TABLE notebooks ADD COLUMN sort_order INTEGER DEFAULT 0"))
        note_cols = _column_names(db, "notes")
        if "is_deleted" not in note_cols:
            db.execute(text("ALTER TABLE notes ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
        if "deleted_at" not in note_cols:
            db.execute(text("ALTER TABLE notes ADD COLUMN deleted_at DATETIME"))
        todo_cols = _column_names(db, "todo_items")
        if "source_anchor_text" not in todo_cols:
            db.execute(text("ALTER TABLE todo_items ADD COLUMN source_anchor_text TEXT"))
        if "due_at" not in todo_cols:
            db.execute(text("ALTER TABLE todo_items ADD COLUMN due_at DATETIME"))
        if "reminder_at" not in todo_cols:
            db.execute(text("ALTER TABLE todo_items ADD COLUMN reminder_at DATETIME"))
        db.commit()
    finally:
        db.close()


_migrate_legacy_schema()


def _init_default_notebooks():
    db = SessionLocal()
    try:
        if db.query(Notebook).count() == 0:
            db.add_all([
                Notebook(name="日记本", icon="📔", sort_order=0),
                Notebook(name="文档", icon="📄", sort_order=1),
            ])
            db.commit()
    finally:
        db.close()


_init_default_notebooks()

TODO_PRIORITIES = {"low", "medium", "high"}


def _normalize_todo_priority(priority: Optional[str]) -> str:
    val = (priority or "medium").strip().lower()
    if val not in TODO_PRIORITIES:
        raise HTTPException(400, "priority 必须是 low / medium / high")
    return val

app = FastAPI(title="交易记录系统")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUTH_COOKIE = "session_token"
AUTH_WHITELIST = {"/api/auth/login", "/api/auth/check", "/api/auth/setup"}
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0" if DEV_MODE else "1") == "1"


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if DEV_MODE:
            return await call_next(request)
        if request.url.path.startswith("/api/") and request.url.path not in AUTH_WHITELIST:
            token = request.cookies.get(AUTH_COOKIE)
            if not token or not verify_token(token):
                return JSONResponse(status_code=401, content={"detail": "未登录"})
        return await call_next(request)


app.add_middleware(AuthMiddleware)


class LoginBody(BaseModel):
    username: str
    password: str


@app.get("/api/auth/check")
def auth_check(request: Request):
    token = request.cookies.get(AUTH_COOKIE)
    if token and verify_token(token):
        return {"authenticated": True, "username": verify_token(token)}
    return {"authenticated": False}


@app.post("/api/auth/setup")
def auth_setup(body: LoginBody):
    if load_credentials():
        raise HTTPException(400, "账号已存在，无法重复初始化")
    save_credentials(body.username, body.password)
    return {"ok": True}


@app.post("/api/auth/login")
def auth_login(body: LoginBody, response: Response):
    if not load_credentials():
        raise HTTPException(400, "请先初始化账号 (POST /api/auth/setup)")
    if not check_login(body.username, body.password):
        raise HTTPException(401, "用户名或密码错误")
    token = create_token(body.username)
    response.set_cookie(
        AUTH_COOKIE, token,
        max_age=7 * 86400, httponly=True, samesite="lax", path="/", secure=COOKIE_SECURE,
    )
    return {"ok": True, "username": body.username}


@app.post("/api/auth/logout")
def auth_logout(response: Response):
    response.delete_cookie(AUTH_COOKIE, path="/")
    return {"ok": True}


# ── Upload ──

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"不支持的文件格式: {ext}")
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"url": f"/api/uploads/{filename}"}


@app.get("/api/uploads/{filename}")
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
    if len(cells) < 10:
        raise ValueError("列数不足，期望10列")
    trade_day = _parse_cn_date(cells[0])
    contract = str(cells[1] or "").strip()
    if not contract:
        raise ValueError("合约为空")
    direction = _map_direction(cells[2])
    category = str(cells[3] or "").strip() or None
    open_price = _parse_float(cells[4], "成交价")
    quantity = _parse_float(cells[5], "手数")
    if quantity <= 0:
        raise ValueError("手数必须大于0")
    _turnover = _parse_float(cells[6], "成交额")
    status = _map_open_close(cells[7])
    commission = _parse_float(cells[8], "手续费")
    pnl = _parse_float(cells[9], "平仓盈亏")
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
    q = db.query(Trade).filter(Trade.instrument_type == "期货", Trade.status == "open")
    if source_keyword:
        q = q.filter(Trade.notes.contains(source_keyword))
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
    text = str(note or "")
    broker = None
    source = None
    m_broker = re.search(r"来源券商:\s*([^|]+)", text)
    if m_broker and m_broker.group(1).strip():
        broker = m_broker.group(1).strip()
    m_source = re.search(r"来源:\s*([^|]+)", text)
    if m_source and m_source.group(1).strip():
        source = m_source.group(1).strip()
    return {"broker_name": broker, "source_label": source}


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
        Trade.instrument_type == "期货",
        Trade.symbol == symbol,
        Trade.direction == close_side,
        Trade.status == "open",
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
            open_commission_total = float(row.commission or 0)
            row.quantity = round(remaining_qty, 6)
            row.commission = round(open_commission_total * (remaining_qty / row_qty), 6)
            row.notes = _append_note(row.notes, "部分平仓后自动拆分")
        remaining -= take


@app.post("/api/trades/import-paste", response_model=TradePasteImportResponse)
def import_trades_from_paste(payload: TradePasteImportRequest, db: Session = Depends(get_db)):
    text = (payload.raw_text or "").strip()
    if not text:
        raise HTTPException(400, "请粘贴交易数据")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise HTTPException(400, "粘贴内容为空")

    inserted = 0
    skipped = 0
    errors: List[TradePasteImportError] = []
    start_idx = 0

    first_cells = [c.strip() for c in lines[0].split("\t")]
    if all(h in first_cells for h in PASTE_TRADE_HEADERS):
        start_idx = 1

    # 1) 先解析并去重
    parsed_rows: List[Dict[str, Any]] = []
    for idx, raw in enumerate(lines[start_idx:], start=start_idx + 1):
        try:
            cells = [c.replace("\xa0", " ").strip() for c in raw.split("\t")]
            trade_obj = _parse_paste_row(cells, payload.broker)
            # 开仓行做去重；平仓行必须参与冲销，不能因历史“独立平仓记录”被跳过
            if trade_obj.status == "open":
                q_exist = db.query(Trade).filter(
                    Trade.trade_date == trade_obj.trade_date,
                    Trade.contract == trade_obj.contract,
                    Trade.direction == trade_obj.direction,
                    Trade.open_price == trade_obj.open_price,
                    Trade.quantity == trade_obj.quantity,
                    Trade.status == trade_obj.status,
                    Trade.commission == trade_obj.commission,
                    Trade.pnl == trade_obj.pnl,
                )
                if payload.broker:
                    q_exist = q_exist.filter(Trade.notes.contains(f"来源券商: {payload.broker}"))
                existed = q_exist.first()
                if existed:
                    skipped += 1
                    continue
            parsed_rows.append({"row": idx, "raw": raw, "trade": trade_obj})
        except Exception as exc:
            errors.append(TradePasteImportError(row=idx, reason=str(exc), raw=raw[:300]))

    # 2) 顺序无关校验：平仓先匹配历史持仓，再匹配本次粘贴开仓
    hist_pool: Dict[str, float] = {}
    q_hist = db.query(Trade).filter(Trade.instrument_type == "期货", Trade.status == "open")
    if payload.broker:
        q_hist = q_hist.filter(Trade.notes.contains(f"来源券商: {payload.broker}"))
    for t in q_hist.all():
        k = _state_key_contract(t.symbol, t.contract, t.direction)
        hist_pool[k] = hist_pool.get(k, 0.0) + float(t.quantity or 0)

    batch_open_pool: Dict[str, float] = {}
    for item in parsed_rows:
        t: Trade = item["trade"]
        if t.status != "open":
            continue
        k = _state_key_contract(t.symbol, t.contract, t.direction)
        batch_open_pool[k] = batch_open_pool.get(k, 0.0) + float(t.quantity or 0)

    valid_rows: List[Dict[str, Any]] = []
    for item in parsed_rows:
        t: Trade = item["trade"]
        if t.status == "open":
            valid_rows.append(item)
            continue
        symbol = _normalize_contract_symbol(t.contract or t.symbol or "")
        side = _position_side(t.direction, "closed")
        k = _state_key_contract(symbol, t.contract, side)
        need = float(t.quantity or 0)
        if need <= 0:
            errors.append(TradePasteImportError(row=item["row"], reason="平仓手数必须大于0", raw=item["raw"][:300]))
            continue
        hist_avail = hist_pool.get(k, 0.0)
        use_hist = min(hist_avail, need)
        hist_pool[k] = hist_avail - use_hist
        remain = need - use_hist
        if remain > 1e-9:
            batch_avail = batch_open_pool.get(k, 0.0)
            use_batch = min(batch_avail, remain)
            batch_open_pool[k] = batch_avail - use_batch
            remain -= use_batch
        if remain > 1e-9:
            errors.append(
                TradePasteImportError(
                    row=item["row"],
                    reason=f"{symbol} {side} 平仓失败：历史与本次粘贴均无足够对应开仓",
                    raw=item["raw"][:300],
                )
            )
            continue
        valid_rows.append(item)

    # 3) 入库：先开仓，后平仓（确保平仓可匹配到本次导入开仓）
    open_rows = [x for x in valid_rows if x["trade"].status == "open"]
    close_rows = [x for x in valid_rows if x["trade"].status == "closed"]
    open_rows.sort(key=lambda x: (x["trade"].trade_date, x["row"]))
    close_rows.sort(key=lambda x: (x["trade"].trade_date, x["row"]))

    for item in open_rows:
        db.add(item["trade"])
        inserted += 1
    db.flush()

    for item in close_rows:
        try:
            _apply_close_fill_to_db(db, item["trade"], broker=payload.broker)
            inserted += 1
        except Exception as exc:
            errors.append(TradePasteImportError(row=item["row"], reason=str(exc), raw=item["raw"][:300]))

    db.commit()
    return TradePasteImportResponse(inserted=inserted, skipped=skipped, errors=errors[:100])


@app.get("/api/trades/positions", response_model=List[TradePositionResponse])
def list_trade_positions(
    symbol: Optional[str] = None,
    source_keyword: Optional[str] = None,
    db: Session = Depends(get_db),
):
    state = _build_position_state_from_db(db, source_keyword=source_keyword)
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


@app.get("/api/trades", response_model=List[TradeResponse])
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
    db: Session = Depends(get_db),
):
    q = db.query(Trade)
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
    if source_keyword:
        q = q.filter(Trade.notes.contains(source_keyword))
    return q.order_by(Trade.open_time.desc()).offset((page - 1) * size).limit(size).all()


@app.get("/api/trades/count")
def count_trades(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    instrument_type: Optional[str] = None,
    symbol: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    strategy_type: Optional[str] = None,
    source_keyword: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Trade)
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
    if source_keyword:
        q = q.filter(Trade.notes.contains(source_keyword))
    return {"total": q.count()}


@app.get("/api/trades/statistics")
def get_statistics(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    instrument_type: Optional[str] = None,
    symbol: Optional[str] = None,
    source_keyword: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Trade).filter(Trade.status == "closed")
    if date_from:
        q = q.filter(Trade.trade_date >= date_from)
    if date_to:
        q = q.filter(Trade.trade_date <= date_to)
    if instrument_type:
        q = q.filter(Trade.instrument_type == instrument_type)
    if symbol:
        q = q.filter(Trade.symbol == symbol)
    if source_keyword:
        q = q.filter(Trade.notes.contains(source_keyword))

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


@app.post("/api/trades", response_model=TradeResponse)
def create_trade(trade: TradeCreate, db: Session = Depends(get_db)):
    obj = Trade(**trade.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@app.get("/api/trades/{trade_id:int}", response_model=TradeResponse)
def get_trade(trade_id: int, db: Session = Depends(get_db)):
    t = db.query(Trade).filter(Trade.id == trade_id).first()
    if not t:
        raise HTTPException(404, "Trade not found")
    return t


@app.put("/api/trades/{trade_id:int}", response_model=TradeResponse)
def update_trade(trade_id: int, data: TradeUpdate, db: Session = Depends(get_db)):
    t = db.query(Trade).filter(Trade.id == trade_id).first()
    if not t:
        raise HTTPException(404, "Trade not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return t


@app.delete("/api/trades/{trade_id:int}")
def delete_trade(trade_id: int, db: Session = Depends(get_db)):
    t = db.query(Trade).filter(Trade.id == trade_id).first()
    if not t:
        raise HTTPException(404, "Trade not found")
    db.delete(t)
    db.commit()
    return {"ok": True}


@app.get("/api/trades/sources")
def list_trade_sources(db: Session = Depends(get_db)):
    values = set()
    broker_rows = db.query(TradeBroker).order_by(TradeBroker.name.asc()).all()
    for b in broker_rows:
        if b.name and b.name.strip():
            values.add(b.name.strip())
    metadata_rows = db.query(TradeSourceMetadata).all()
    for row in metadata_rows:
        if row.broker_name and row.broker_name.strip():
            values.add(row.broker_name.strip())
        if row.source_label and row.source_label.strip():
            values.add(row.source_label.strip())
    note_rows = db.query(Trade.notes).filter(Trade.notes.isnot(None)).all()
    for (note,) in note_rows:
        parsed = _extract_source_from_notes(note)
        if parsed["broker_name"]:
            values.add(parsed["broker_name"])
    return {"items": sorted(values)}


@app.get("/api/trade-review-taxonomy", response_model=TradeReviewTaxonomyResponse)
def get_trade_review_taxonomy():
    return TradeReviewTaxonomyResponse(**trade_review_taxonomy())


@app.get("/api/trades/{trade_id:int}/review", response_model=TradeReviewResponse)
def get_trade_review(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(404, "Trade not found")
    review = db.query(TradeReview).filter(TradeReview.trade_id == trade_id).first()
    if not review:
        raise HTTPException(404, "Trade review not found")
    return review


@app.put("/api/trades/{trade_id:int}/review", response_model=TradeReviewResponse)
def upsert_trade_review(trade_id: int, data: TradeReviewUpsert, db: Session = Depends(get_db)):
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(404, "Trade not found")

    review = db.query(TradeReview).filter(TradeReview.trade_id == trade_id).first()
    if not review:
        review = TradeReview(trade_id=trade_id)
        db.add(review)

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(review, k, v)
    db.commit()
    db.refresh(review)
    return review


@app.delete("/api/trades/{trade_id:int}/review")
def delete_trade_review(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(404, "Trade not found")
    review = db.query(TradeReview).filter(TradeReview.trade_id == trade_id).first()
    if not review:
        return {"ok": True}
    db.delete(review)
    db.commit()
    return {"ok": True}


@app.get("/api/trades/{trade_id:int}/source-metadata", response_model=TradeSourceMetadataResponse)
def get_trade_source_metadata(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
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


@app.put("/api/trades/{trade_id:int}/source-metadata", response_model=TradeSourceMetadataResponse)
def upsert_trade_source_metadata(trade_id: int, data: TradeSourceMetadataUpsert, db: Session = Depends(get_db)):
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
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


@app.get("/api/trade-brokers", response_model=List[TradeBrokerResponse])
def list_trade_brokers(db: Session = Depends(get_db)):
    return db.query(TradeBroker).order_by(TradeBroker.updated_at.desc(), TradeBroker.id.desc()).all()


@app.post("/api/trade-brokers", response_model=TradeBrokerResponse)
def create_trade_broker(data: TradeBrokerCreate, db: Session = Depends(get_db)):
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(400, "名称不能为空")
    existed = db.query(TradeBroker).filter(TradeBroker.name == name).first()
    if existed:
        raise HTTPException(400, "该名称已存在")
    obj = TradeBroker(
        name=name,
        account=(data.account or "").strip() or None,
        password=(data.password or "").strip() or None,
        extra_info=(data.extra_info or "").strip() or None,
        notes=(data.notes or "").strip() or None,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@app.put("/api/trade-brokers/{broker_id}", response_model=TradeBrokerResponse)
def update_trade_broker(broker_id: int, data: TradeBrokerUpdate, db: Session = Depends(get_db)):
    obj = db.query(TradeBroker).filter(TradeBroker.id == broker_id).first()
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


@app.delete("/api/trade-brokers/{broker_id}")
def delete_trade_broker(broker_id: int, db: Session = Depends(get_db)):
    obj = db.query(TradeBroker).filter(TradeBroker.id == broker_id).first()
    if not obj:
        raise HTTPException(404, "券商不存在")
    db.delete(obj)
    db.commit()
    return {"ok": True}


# ── Review ──


@app.get("/api/reviews", response_model=List[ReviewResponse])
def list_reviews(
    review_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Review)
    if review_type:
        q = q.filter(Review.review_type == review_type)
    if date_from:
        q = q.filter(Review.review_date >= date_from)
    if date_to:
        q = q.filter(Review.review_date <= date_to)
    return q.order_by(Review.review_date.desc()).offset((page - 1) * size).limit(size).all()


@app.post("/api/reviews", response_model=ReviewResponse)
def create_review(review: ReviewCreate, db: Session = Depends(get_db)):
    obj = Review(**review.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@app.get("/api/reviews/{review_id}", response_model=ReviewResponse)
def get_review(review_id: int, db: Session = Depends(get_db)):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r:
        raise HTTPException(404, "Review not found")
    return r


@app.put("/api/reviews/{review_id}", response_model=ReviewResponse)
def update_review(review_id: int, data: ReviewUpdate, db: Session = Depends(get_db)):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r:
        raise HTTPException(404, "Review not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    db.commit()
    db.refresh(r)
    return r


@app.delete("/api/reviews/{review_id}")
def delete_review(review_id: int, db: Session = Depends(get_db)):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r:
        raise HTTPException(404, "Review not found")
    db.delete(r)
    db.commit()
    return {"ok": True}


# ── Notebook ──


@app.get("/api/notebooks", response_model=List[NotebookResponse])
def list_notebooks(db: Session = Depends(get_db)):
    return db.query(Notebook).order_by(Notebook.sort_order, Notebook.id).all()


@app.post("/api/notebooks", response_model=NotebookResponse)
def create_notebook(data: NotebookCreate, db: Session = Depends(get_db)):
    obj = Notebook(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@app.put("/api/notebooks/{nb_id}", response_model=NotebookResponse)
def update_notebook(nb_id: int, data: NotebookUpdate, db: Session = Depends(get_db)):
    nb = db.query(Notebook).filter(Notebook.id == nb_id).first()
    if not nb:
        raise HTTPException(404, "Notebook not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(nb, k, v)
    db.commit()
    db.refresh(nb)
    return nb


@app.delete("/api/notebooks/{nb_id}")
def delete_notebook(nb_id: int, db: Session = Depends(get_db)):
    nb = db.query(Notebook).filter(Notebook.id == nb_id).first()
    if not nb:
        raise HTTPException(404, "Notebook not found")
    db.delete(nb)
    db.commit()
    return {"ok": True}


# ── Note ──


@app.get("/api/notes", response_model=List[NoteResponse])
def list_notes(
    notebook_id: Optional[int] = None,
    note_type: Optional[str] = None,
    note_date: Optional[str] = None,
    keyword: Optional[str] = None,
    tag: Optional[str] = None,
    is_pinned: Optional[bool] = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Note).filter(Note.is_deleted == False)  # noqa: E712
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


@app.get("/api/notes/stats")
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


@app.get("/api/notes/history-today")
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


@app.get("/api/notes/diary-tree")
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


_index_links_for_existing_notes()


@app.get("/api/notes/search")
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


@app.get("/api/notes/resolve-link")
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


@app.get("/api/notes/{note_id}/backlinks")
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


@app.get("/api/notes/diary-summaries")
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


@app.get("/api/notes/calendar")
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


@app.post("/api/notes", response_model=NoteResponse)
def create_note(data: NoteCreate, db: Session = Depends(get_db)):
    nb = db.query(Notebook).filter(Notebook.id == data.notebook_id).first()
    if not nb:
        raise HTTPException(404, "Notebook not found")
    obj = Note(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    _index_note_links(db, obj)
    _refresh_link_targets(db)
    db.commit()
    return obj


@app.get("/api/notes/{note_id}", response_model=NoteResponse)
def get_note(note_id: int, db: Session = Depends(get_db)):
    n = db.query(Note).filter(Note.id == note_id, Note.is_deleted == False).first()  # noqa: E712
    if not n:
        raise HTTPException(404, "Note not found")
    return n


@app.put("/api/notes/{note_id}", response_model=NoteResponse)
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


@app.delete("/api/notes/{note_id}")
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


@app.get("/api/recycle/notes", response_model=List[NoteResponse])
def list_recycle_notes(
    note_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Note).filter(Note.is_deleted == True)  # noqa: E712
    if note_type:
        q = q.filter(Note.note_type == note_type)
    return q.order_by(Note.deleted_at.desc()).all()


@app.post("/api/recycle/notes/{note_id}/restore", response_model=NoteResponse)
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


@app.delete("/api/recycle/notes/{note_id}/purge")
def purge_note(note_id: int, db: Session = Depends(get_db)):
    n = db.query(Note).filter(Note.id == note_id).first()
    if not n:
        raise HTTPException(404, "Note not found")
    db.query(NoteLink).filter(NoteLink.source_note_id == note_id).delete(synchronize_session=False)
    db.query(NoteLink).filter(NoteLink.target_note_id == note_id).delete(synchronize_session=False)
    db.delete(n)
    db.commit()
    return {"ok": True}


@app.delete("/api/recycle/notes/clear")
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


@app.get("/api/todos", response_model=List[TodoResponse])
def list_todos(
    include_completed: bool = Query(True),
    keyword: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(TodoItem)
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


@app.post("/api/todos", response_model=TodoResponse)
def create_todo(data: TodoCreate, db: Session = Depends(get_db)):
    content = (data.content or "").strip()
    if not content:
        raise HTTPException(400, "待办内容不能为空")
    priority = _normalize_todo_priority(data.priority)
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
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@app.put("/api/todos/{todo_id}", response_model=TodoResponse)
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


@app.delete("/api/todos/{todo_id}")
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


@app.get("/api/poem/daily")
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



# ── News ──

NEWS_REPO = os.environ.get("ECONOMIST_REPO", "Yv6GtreV/TheEconomistDownload")
NEWS_BRANCH = os.environ.get("ECONOMIST_BRANCH", "main")
NEWS_DATA_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "data" / "news_epub"
NEWS_DATA_DIR.mkdir(parents=True, exist_ok=True)

TRANSLATE_PROVIDER = os.environ.get("TRANSLATE_PROVIDER", "auto")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODELS = [m.strip() for m in os.environ.get("DEEPSEEK_MODELS", f"{DEEPSEEK_MODEL},deepseek-v3").split(",") if m.strip()]

_news_progress_lock = threading.Lock()
_news_translate_progress: dict[int, dict] = {}

_today_news_lock = threading.Lock()
_today_news_cache = {"updated_at": None, "payload": None}
TODAY_NEWS_CACHE_TTL = int(os.environ.get("TODAY_NEWS_CACHE_TTL", "900"))
TODAY_NEWS_SOURCE_BLOCKLIST = {"时政微周刊"}
_article_content_cache = {}
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

TODAY_NEWS_FEEDS = {
    "经济": [
        ("Google News 中文", "https://news.google.com/rss/search?q=%E7%BB%8F%E6%B5%8E&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
        ("Google News 财经", "https://news.google.com/rss/search?q=%E8%B4%A2%E7%BB%8F&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ],
    "时政": [
        ("Google News 时政", "https://news.google.com/rss/search?q=%E6%97%B6%E6%94%BF&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
        ("Google News 国际", "https://news.google.com/rss/search?q=%E5%9B%BD%E9%99%85+%E6%94%BF%E6%B2%BB&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ],
    "AI": [
        ("Google News AI", "https://news.google.com/rss/search?q=AI&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
        ("Google News 人工智能", "https://news.google.com/rss/search?q=%E4%BA%BA%E5%B7%A5%E6%99%BA%E8%83%BD&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ],
    "科技": [
        ("Google News 科技", "https://news.google.com/rss/search?q=%E7%A7%91%E6%8A%80&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
        ("Google News 芯片", "https://news.google.com/rss/search?q=%E8%8A%AF%E7%89%87&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ],
}


def _extract_issue_date(name: str) -> Optional[date]:
    candidates = [
        r"(20\d{2})[-_\.](\d{1,2})[-_\.](\d{1,2})",
        r"(20\d{2})(\d{2})(\d{2})",
    ]
    for pattern in candidates:
        m = re.search(pattern, name)
        if not m:
            continue
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, d)
        except Exception:
            return None
    return None


def _parse_epub_text(epub_path: Path) -> str:
    book = epub.read_epub(str(epub_path))
    sections = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        for bad in soup(["script", "style", "nav"]):
            bad.decompose()
        text = soup.get_text("\n", strip=True)
        text = html.unescape(text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        if len(text) > 60:
            sections.append(text)
    return _clean_extracted_text("\n\n".join(sections))


def _clean_extracted_text(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    filtered = []
    noise = (
        "the economist", "contents", "leader", "letters", "briefing",
        "subscribe", "print edition", "digital edition", "downloaded from",
    )

    for ln in lines:
        low = ln.lower()
        if len(ln) < 2:
            continue
        if sum(ch.isdigit() for ch in ln) >= max(5, len(ln) // 2):
            continue
        if any(k in low for k in noise) and len(ln) < 60:
            continue
        filtered.append(ln)

    dedup = []
    seen = set()
    for ln in filtered:
        key = ln.lower()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(ln)

    return "\n\n".join(dedup)


def _split_text_chunks(text: str, max_len: int = 2800) -> List[str]:
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    buf = ""
    for p in paras:
        if len(buf) + len(p) + 2 <= max_len:
            buf = f"{buf}\n\n{p}".strip()
        else:
            if buf:
                chunks.append(buf)
            if len(p) <= max_len:
                buf = p
            else:
                for i in range(0, len(p), max_len):
                    chunks.append(p[i:i + max_len])
                buf = ""
    if buf:
        chunks.append(buf)
    return chunks


def _translate_with_openai_compatible(api_key: str, base_url: str, model: str, text: str) -> str:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是专业财经翻译。将英文翻译为准确、流畅、简洁的中文，保留原段落结构。"
                    "术语要求：yield curve=收益率曲线，basis points=个基点，"
                    "fiscal deficit=财政赤字，current-account deficit=经常账户赤字，"
                    "quantitative easing=量化宽松。"
                    "机构、人名、地名首次出现可保留英文括号。不要添加解释和总结。"
                ),
            },
            {"role": "user", "content": text},
        ],
        "temperature": 0.1,
    }
    with httpx.Client(timeout=120) as client:
        resp = client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        if resp.status_code >= 400:
            detail = ""
            try:
                detail = resp.json().get("error", {}).get("message", "")
            except Exception:
                detail = resp.text[:500]
            raise HTTPException(resp.status_code, f"模型请求失败({resp.status_code}): {detail or resp.text[:300]}")
        data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def _translate_with_deepseek_fallback(chunk: str) -> str:
    last_err = None
    base_candidates = [DEEPSEEK_BASE_URL, "https://api.deepseek.com", "https://api.deepseek.com/v1"]
    for base in base_candidates:
        for model in DEEPSEEK_MODELS:
            try:
                return _translate_with_openai_compatible(
                    DEEPSEEK_API_KEY,
                    base,
                    model,
                    chunk,
                )
            except HTTPException as e:
                last_err = e
                continue
            except Exception as e:
                last_err = e
                continue
    if isinstance(last_err, HTTPException):
        raise last_err
    raise HTTPException(500, f"DeepSeek 调用失败: {last_err}")


def _chunk_cache_dir() -> Path:
    d = NEWS_DATA_DIR / "translation_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _chunk_cache_key(chunk: str) -> str:
    raw = f"{TRANSLATE_PROVIDER}|{DEEPSEEK_MODEL}|{OPENAI_MODEL}|{chunk}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _translate_chunk_cached(chunk: str) -> str:
    cache_file = _chunk_cache_dir() / f"{_chunk_cache_key(chunk)}.txt"
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")

    provider = TRANSLATE_PROVIDER.lower()
    last_err = None

    for _ in range(3):
        try:
            if provider in ("auto", "deepseek") and DEEPSEEK_API_KEY:
                text = _translate_with_openai_compatible(
                    DEEPSEEK_API_KEY,
                    "https://api.deepseek.com",
                    DEEPSEEK_MODEL,
                    chunk,
                )
                cache_file.write_text(text, encoding="utf-8")
                return text

            if provider in ("auto", "openai") and OPENAI_API_KEY:
                text = _translate_with_openai_compatible(
                    OPENAI_API_KEY,
                    OPENAI_BASE_URL,
                    OPENAI_MODEL,
                    chunk,
                )
                cache_file.write_text(text, encoding="utf-8")
                return text

            raise HTTPException(400, "未配置翻译 API Key，请设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY")
        except Exception as e:
            last_err = e

    raise HTTPException(500, f"翻译分块失败: {last_err}")


def _translate_text(text: str, progress_cb=None) -> str:
    chunks = _split_text_chunks(text)
    if not chunks:
        if progress_cb:
            progress_cb(0, 0)
        return ""

    workers = int(os.environ.get("TRANSLATE_MAX_WORKERS", "4"))
    workers = max(1, min(8, workers))
    results = [""] * len(chunks)
    done = 0
    total = len(chunks)

    if progress_cb:
        progress_cb(done, total)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        fut_map = {pool.submit(_translate_chunk_cached, chunk): idx for idx, chunk in enumerate(chunks)}
        for fut in as_completed(fut_map):
            idx = fut_map[fut]
            try:
                results[idx] = fut.result()
            except HTTPException as e:
                detail = str(e.detail)
                if "Content Exists Risk" in detail:
                    results[idx] = f"[本段触发模型风控，保留原文]\n\n{chunks[idx]}"
                else:
                    raise
            done += 1
            if progress_cb:
                progress_cb(done, total)

    return "\n\n".join(results)


def _extract_latest_entry_from_readme(readme_text: str) -> dict:
    pattern = re.compile(
        r"^##\s+(.+?)\s*$\n(?:-|\*)\s*\[EBOOK\]\((https?://[^)]+)\)",
        re.MULTILINE,
    )
    matches = pattern.findall(readme_text)
    if not matches:
        raise HTTPException(404, "来源仓库 README 中未找到 EBOOK 链接")

    candidates = []
    for title, url in matches:
        issue_dt = _extract_issue_date(title)
        if not issue_dt:
            continue
        candidates.append((issue_dt, title.strip(), url.strip()))

    if not candidates:
        raise HTTPException(404, "README 中未找到可识别日期的 EBOOK 条目")

    candidates.sort(key=lambda x: x[0], reverse=True)
    issue_dt, issue_title, ebook_url = candidates[0]
    return {
        "issue_date": issue_dt,
        "title": issue_title,
        "ebook_url": ebook_url,
    }


def _google_drive_direct_download(url: str) -> str:
    m = re.search(r"/d/([^/]+)", url)
    if not m:
        return url
    file_id = m.group(1)
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def _download_latest_issue() -> dict:
    if "/" not in NEWS_REPO:
        raise HTTPException(400, "ECONOMIST_REPO 格式错误，应为 owner/repo")

    owner, repo = NEWS_REPO.split("/", 1)
    readme_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{NEWS_BRANCH}/README.md"

    with httpx.Client(timeout=60, follow_redirects=True) as client:
        readme_resp = client.get(readme_url)
        readme_resp.raise_for_status()
        latest = _extract_latest_entry_from_readme(readme_resp.text)

        filename = f"{latest['issue_date']}.epub"
        local_path = NEWS_DATA_DIR / filename
        download_url = _google_drive_direct_download(latest["ebook_url"])

        dl_resp = client.get(download_url)
        dl_resp.raise_for_status()
        local_path.write_bytes(dl_resp.content)

    parsed_text = _parse_epub_text(local_path)

    return {
        "title": latest["title"],
        "issue_date": latest["issue_date"],
        "source_repo": NEWS_REPO,
        "source_path": latest["title"],
        "source_sha": None,
        "source_url": latest["ebook_url"],
        "local_epub_path": str(local_path),
        "content_en": parsed_text,
    }


@app.post("/api/news/sync", response_model=NewsIssueResponse)
def sync_latest_news(db: Session = Depends(get_db)):
    latest = _download_latest_issue()

    issue = db.query(NewsIssue).filter(NewsIssue.source_path == latest["source_path"]).first()
    if not issue:
        issue = NewsIssue(**latest, status="downloaded")
        db.add(issue)
    else:
        for k, v in latest.items():
            setattr(issue, k, v)
        issue.status = "downloaded"

    db.commit()
    db.refresh(issue)
    return issue


@app.get("/api/news/issues", response_model=List[NewsIssueResponse])
def list_news_issues(db: Session = Depends(get_db)):
    return db.query(NewsIssue).order_by(NewsIssue.issue_date.desc(), NewsIssue.updated_at.desc()).all()


@app.get("/api/news/issues/{issue_id}", response_model=NewsIssueDetailResponse)
def get_news_issue(issue_id: int, db: Session = Depends(get_db)):
    issue = db.query(NewsIssue).filter(NewsIssue.id == issue_id).first()
    if not issue:
        raise HTTPException(404, "News issue not found")
    return issue


@app.delete("/api/news/issues/{issue_id}")
def delete_news_issue(issue_id: int, db: Session = Depends(get_db)):
    issue = db.query(NewsIssue).filter(NewsIssue.id == issue_id).first()
    if not issue:
        raise HTTPException(404, "News issue not found")

    local_path = (issue.local_epub_path or "").strip()
    if local_path:
        try:
            p = Path(local_path)
            if p.exists() and p.is_file():
                p.unlink()
        except Exception:
            pass

    db.delete(issue)
    db.commit()

    with _news_progress_lock:
        _news_translate_progress.pop(issue_id, None)

    return {"ok": True}


@app.post("/api/news/issues/{issue_id}/translate", response_model=NewsIssueDetailResponse)
def translate_news_issue(issue_id: int, db: Session = Depends(get_db)):
    issue = db.query(NewsIssue).filter(NewsIssue.id == issue_id).first()
    if not issue:
        raise HTTPException(404, "News issue not found")
    if not issue.content_en:
        raise HTTPException(400, "当前期刊没有可翻译内容")

    issue.status = "translating"
    db.commit()

    def _progress(done: int, total: int):
        pct = 100 if total == 0 else round(done * 100 / total, 2)
        with _news_progress_lock:
            _news_translate_progress[issue_id] = {
                "issue_id": issue_id,
                "status": "translating",
                "done": done,
                "total": total,
                "percent": pct,
                "message": f"正在翻译 {done}/{total}",
                "updated_at": datetime.now().isoformat(),
            }

    try:
        _progress(0, 0)
        translated = _translate_text(issue.content_en, progress_cb=_progress)
        issue.content_zh = translated
        issue.translated_at = datetime.now()
        issue.status = "translated"
        db.commit()
        db.refresh(issue)
        with _news_progress_lock:
            total = _news_translate_progress.get(issue_id, {}).get("total", 0)
            _news_translate_progress[issue_id] = {
                "issue_id": issue_id,
                "status": "translated",
                "done": total,
                "total": total,
                "percent": 100,
                "message": "翻译完成",
                "updated_at": datetime.now().isoformat(),
            }
        return issue
    except HTTPException as e:
        issue.status = "downloaded"
        db.commit()
        with _news_progress_lock:
            prev = _news_translate_progress.get(issue_id, {})
            _news_translate_progress[issue_id] = {
                "issue_id": issue_id,
                "status": "failed",
                "done": prev.get("done", 0),
                "total": prev.get("total", 0),
                "percent": prev.get("percent", 0),
                "message": str(e.detail),
                "updated_at": datetime.now().isoformat(),
            }
        raise
    except Exception as e:
        issue.status = "downloaded"
        db.commit()
        with _news_progress_lock:
            prev = _news_translate_progress.get(issue_id, {})
            _news_translate_progress[issue_id] = {
                "issue_id": issue_id,
                "status": "failed",
                "done": prev.get("done", 0),
                "total": prev.get("total", 0),
                "percent": prev.get("percent", 0),
                "message": str(e),
                "updated_at": datetime.now().isoformat(),
            }
        raise HTTPException(500, f"翻译失败: {e}")


@app.get("/api/news/issues/{issue_id}/progress")
def get_news_translate_progress(issue_id: int):
    with _news_progress_lock:
        p = _news_translate_progress.get(issue_id)
    if p:
        return p
    return {
        "issue_id": issue_id,
        "status": "idle",
        "done": 0,
        "total": 0,
        "percent": 0,
        "message": "未开始",
        "updated_at": datetime.now().isoformat(),
    }


def _parse_rss_feed(xml_text: str, fallback_source: str, limit: int = 10) -> List[dict]:
    out = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return out

    channel = root.find("channel")
    if channel is None:
        return out

    channel_title = channel.findtext("title") or fallback_source

    for item in channel.findall("item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue

        source = fallback_source
        src_node = item.find("source")
        if src_node is not None and (src_node.text or "").strip():
            source = src_node.text.strip()
        else:
            source = channel_title

        summary_raw = (item.findtext("description") or "").strip()
        summary = BeautifulSoup(summary_raw, "html.parser").get_text(" ", strip=True)[:240]

        published_at = None
        pub_raw = (item.findtext("pubDate") or "").strip()
        if pub_raw:
            try:
                published_at = parsedate_to_datetime(pub_raw).isoformat()
            except Exception:
                published_at = pub_raw

        out.append({
            "title": title,
            "url": link,
            "source": source,
            "published_at": published_at,
            "summary": summary,
        })

    return out


def _fetch_today_feed(source_name: str, feed_url: str, limit: int) -> List[dict]:
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            resp = client.get(feed_url)
            resp.raise_for_status()
        return _parse_rss_feed(resp.text, source_name, limit=limit)
    except Exception:
        return []


def _extract_article_text_from_html(html_text: str) -> str:
    soup = BeautifulSoup(html_text, "html.parser")
    for bad in soup(["script", "style", "noscript", "nav", "footer", "header", "aside"]):
        bad.decompose()

    article = soup.find("article")
    container = article or soup.find("main") or soup.body or soup

    paragraphs = []
    for p in container.find_all("p"):
        txt = p.get_text(" ", strip=True)
        if len(txt) >= 20:
            paragraphs.append(txt)
    if not paragraphs:
        txt = container.get_text("\n", strip=True)
        txt = re.sub(r"\n{3,}", "\n\n", txt)
        return txt[:12000]
    return "\n\n".join(paragraphs)[:12000]


def _fetch_article_content(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(400, "URL 非法")

    cached = _article_content_cache.get(url)
    if cached and (_time.time() - cached["ts"] < 3600):
        return cached["data"]

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()
        html_text = resp.text

    soup = BeautifulSoup(html_text, "html.parser")
    title = (soup.title.get_text(strip=True) if soup.title else "").strip()
    content = _extract_article_text_from_html(html_text)
    data = {"url": url, "title": title, "content": content}
    _article_content_cache[url] = {"ts": _time.time(), "data": data}
    return data


def _build_today_news(limit_per_category: int = 8) -> dict:
    categories = []

    for cat, feeds in TODAY_NEWS_FEEDS.items():
        merged = []
        for source_name, feed_url in feeds:
            merged.extend(_fetch_today_feed(source_name, feed_url, limit_per_category))

        dedup = []
        seen = set()
        for item in merged:
            source_name = (item.get("source") or "").strip()
            if source_name in TODAY_NEWS_SOURCE_BLOCKLIST:
                continue
            key = item.get("url") or item.get("title")
            if not key or key in seen:
                continue
            seen.add(key)
            dedup.append(item)

        dedup.sort(key=lambda x: x.get("published_at") or "", reverse=True)

        categories.append({
            "name": cat,
            "items": dedup[:limit_per_category],
        })

    return {
        "updated_at": datetime.now().isoformat(),
        "categories": categories,
    }


@app.get("/api/news/today")
def get_today_news(
    force_refresh: bool = Query(False),
    limit: int = Query(8, ge=3, le=20),
):
    now_ts = _time.time()

    with _today_news_lock:
        cached = _today_news_cache.get("payload")
        updated_at = _today_news_cache.get("updated_at")
        if not force_refresh and cached and updated_at and (now_ts - updated_at) < TODAY_NEWS_CACHE_TTL:
            return cached

    payload = _build_today_news(limit_per_category=limit)

    with _today_news_lock:
        _today_news_cache["updated_at"] = now_ts
        _today_news_cache["payload"] = payload

    return payload


@app.get("/api/news/article-content")
def get_news_article_content(url: str = Query(..., min_length=8)):
    try:
        return _fetch_article_content(url)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"抓取原文失败: {e}")


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
_monitor_thread.start()


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


@app.get("/api/monitor/realtime")
def monitor_realtime():
    return {
        "system": _get_system_info(),
        "cpu": _get_cpu_info(),
        "memory": _get_memory_info(),
        "disk": _get_disk_info(),
        "network": _get_network_info(),
        "processes": _get_top_processes(),
        "services": _get_services_status(),
    }


@app.get("/api/monitor/history")
def monitor_history():
    return list(_monitor_history)
