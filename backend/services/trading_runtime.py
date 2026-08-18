from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.db import get_db
from models import Trade, TradeInstrument, TradeReview, TradeSourceMetadata
from models.review import TradePlan, TradePlanTradeLink
from schemas import (
    TradeCreate,
    TradePositionResponse,
    TradeReviewTaxonomyResponse,
    TradeReviewUpsert,
    TradeSearchOptionItemResponse,
    TradeSearchOptionsResponse,
    TradeSourceMetadataResponse,
    TradeSourceMetadataUpsert,
    TradeUpdate,
)
from services import runtime as legacy_runtime
from services.utility_runtime import cleanup_unreferenced_uploads
from trade_review_taxonomy import trade_review_taxonomy
from trading.source_service import (
    apply_source_keyword_filter as _source_apply_source_keyword_filter,
    attach_trade_view_fields as _source_attach_trade_view_fields,
    upsert_trade_source_metadata_for_import as _source_upsert_trade_source_metadata_for_import,
)
from trading.risk_point_service import add_risk_point_snapshot, tracked_trade_values_changed
from trading.currency_service import normalize_trade_currency_values
from trading.tag_service import (
    attach_trade_review_tags as _attach_trade_review_tags,
    normalize_tag_list as _normalize_tag_list,
    serialize_legacy_tags as _serialize_legacy_tags,
    sync_trade_review_tags as _sync_trade_review_tags,
)


def _normalize_contract_symbol(contract: str) -> str:
    value = (contract or "").strip()
    match = re.match(r"([A-Za-z]+)", value)
    if match:
        return match.group(1).upper()
    return value


def _position_side(direction: str, status: str) -> str:
    if status == "open":
        return "做多" if direction == "做多" else "做空"
    return "做空" if direction == "做多" else "做多"


def _state_key(symbol: str, side: str) -> str:
    return f"{symbol}::{side}"


def _state_key_contract(symbol: str, contract: Optional[str], side: str) -> str:
    contract_value = re.sub(r"\s+", "", (contract or "").strip()).upper()
    return f"{symbol}::{contract_value}::{side}"


def _ensure_symbol_state(
    state: Dict[str, Dict[str, Any]],
    symbol: str,
    side: str,
    contract: Optional[str],
    trade_day,
):
    key = _state_key(symbol, side)
    if key not in state:
        state[key] = {
            "symbol": symbol,
            "side": side,
            "contract": contract,
            "price_total": 0.0,
            "record_count": 0,
            "avg_open_price": 0.0,
            "open_since": None,
            "last_trade_date": trade_day,
            "commission": 0.0,
            "leverage": None,
        }
    current = state[key]
    if contract:
        current["contract"] = contract
    current["last_trade_date"] = trade_day
    return current


def _build_position_state_from_db(db: Session, source_keyword: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    state: Dict[str, Dict[str, Any]] = {}
    query = db.query(Trade).filter(Trade.is_deleted == False, Trade.status == "open")  # noqa: E712
    query = _apply_source_keyword_filter(query, source_keyword)
    rows = query.order_by(Trade.open_time.asc(), Trade.id.asc()).all()
    for row in rows:
        symbol = _normalize_contract_symbol(row.contract or row.symbol or "")
        side = row.direction
        current = _ensure_symbol_state(state, symbol, side, row.contract, row.trade_date)
        current["price_total"] += float(row.open_price or 0)
        current["record_count"] += 1
        current["avg_open_price"] = current["price_total"] / current["record_count"]
        current["commission"] = float(current.get("commission") or 0) + float(row.commission or 0)
        if current.get("leverage") is None and getattr(row, "leverage", None) is not None:
            current["leverage"] = row.leverage
        if current["open_since"] is None:
            current["open_since"] = row.trade_date
        if row.open_time and (current["last_trade_date"] is None or row.trade_date >= current["last_trade_date"]):
            current["last_trade_date"] = row.trade_date
    return state


def _build_position_state_from_db_with_owner_role(
    db: Session,
    source_keyword: Optional[str] = None,
    owner_role: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    state: Dict[str, Dict[str, Any]] = {}
    query = db.query(Trade).filter(Trade.is_deleted == False, Trade.status == "open")  # noqa: E712
    role_filter = legacy_runtime._owner_role_filter_for_admin(Trade, owner_role)
    if role_filter is not None:
        query = query.filter(role_filter)
    query = _apply_source_keyword_filter(query, source_keyword)
    rows = query.order_by(Trade.open_time.asc(), Trade.id.asc()).all()
    for row in rows:
        symbol = _normalize_contract_symbol(row.contract or row.symbol or "")
        side = row.direction
        current = _ensure_symbol_state(state, symbol, side, row.contract, row.trade_date)
        current["price_total"] += float(row.open_price or 0)
        current["record_count"] += 1
        current["avg_open_price"] = current["price_total"] / current["record_count"]
        current["commission"] = float(current.get("commission") or 0) + float(row.commission or 0)
        if current.get("leverage") is None and getattr(row, "leverage", None) is not None:
            current["leverage"] = row.leverage
        if current["open_since"] is None:
            current["open_since"] = row.trade_date
        if row.open_time and (current["last_trade_date"] is None or row.trade_date >= current["last_trade_date"]):
            current["last_trade_date"] = row.trade_date
    return state


def _attach_trade_view_fields(db: Session, rows: List[Trade]) -> List[Trade]:
    return _source_attach_trade_view_fields(db, rows)


def _apply_source_keyword_filter(query, source_keyword: Optional[str]):
    return _source_apply_source_keyword_filter(query, source_keyword)


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


def _apply_trade_filters(
    query,
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    instrument_type: Optional[str] = None,
    symbol: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    strategy_type: Optional[str] = None,
    source_keyword: Optional[str] = None,
    owner_role: Optional[str] = None,
):
    role_filter = legacy_runtime._owner_role_filter_for_admin(Trade, owner_role)
    if role_filter is not None:
        query = query.filter(role_filter)
    if date_from:
        query = query.filter(Trade.trade_date >= date_from)
    if date_to:
        query = query.filter(Trade.trade_date <= date_to)
    if instrument_type:
        query = query.filter(Trade.instrument_type == instrument_type)
    if symbol:
        query = query.filter(Trade.symbol == symbol)
    if direction:
        query = query.filter(Trade.direction == direction)
    if status:
        query = query.filter(Trade.status == status)
    if strategy_type:
        query = query.filter(Trade.strategy_type == strategy_type)
    return _apply_source_keyword_filter(query, source_keyword)


def _parse_include_ids(include_ids: Optional[str]) -> List[int]:
    if not include_ids:
        return []
    items: List[int] = []
    seen = set()
    for part in str(include_ids).split(","):
        raw = part.strip()
        if not raw or not raw.isdigit():
            continue
        value = int(raw)
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        items.append(value)
    return items


def list_trade_positions(
    symbol: Optional[str] = None,
    source_keyword: Optional[str] = None,
    owner_role: Optional[str] = None,
    db: Session = Depends(get_db),
):
    state = _build_position_state_from_db_with_owner_role(db, source_keyword=source_keyword, owner_role=owner_role)
    items = []
    for current in state.values():
        if symbol and current["symbol"] != symbol:
            continue
        items.append(
            TradePositionResponse(
                symbol=current["symbol"],
                contract=current.get("contract"),
                side=current.get("side") or "做多",
                avg_open_price=round(float(current.get("avg_open_price") or 0), 4),
                open_since=current.get("open_since"),
                commission=round(float(current.get("commission") or 0), 2),
                leverage=current.get("leverage"),
            )
        )
    items.sort(key=lambda item: (item.symbol, item.side))
    return items


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
    owner_role: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Trade).filter(Trade.is_deleted == False)  # noqa: E712
    query = _apply_trade_filters(
        query,
        date_from=date_from,
        date_to=date_to,
        instrument_type=instrument_type,
        symbol=symbol,
        direction=direction,
        status=status,
        strategy_type=strategy_type,
        source_keyword=source_keyword,
        owner_role=owner_role,
    )
    query = query.order_by(Trade.open_time.desc())
    rows = query.offset((page - 1) * size).limit(size).all()
    return _attach_trade_view_fields(db, rows)


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
    role_filter = legacy_runtime._owner_role_filter_for_admin(Trade, owner_role)
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
        conditions = [
            Trade.symbol.contains(keyword.upper()),
            Trade.contract.contains(keyword),
            TradeSourceMetadata.broker_name.contains(keyword),
            TradeSourceMetadata.source_label.contains(keyword),
        ]
        if keyword.isdigit():
            conditions.append(Trade.id == int(keyword))
        query = query.filter(or_(*conditions))

    rows = query.order_by(Trade.open_time.desc(), Trade.id.desc()).limit(limit).all()
    ordered_rows = _attach_trade_view_fields(db, rows)
    collected_ids = {row.id for row in ordered_rows if row.id}

    missing_ids = [trade_id for trade_id in include_trade_ids if trade_id not in collected_ids]
    if missing_ids:
        include_query = db.query(Trade).filter(Trade.id.in_(missing_ids), Trade.is_deleted == False)  # noqa: E712
        include_role_filter = legacy_runtime._owner_role_filter_for_admin(Trade, owner_role)
        if include_role_filter is not None:
            include_query = include_query.filter(include_role_filter)
        include_rows = _attach_trade_view_fields(
            db,
            include_query.order_by(Trade.open_time.desc(), Trade.id.desc()).all(),
        )
        include_map = {row.id: row for row in include_rows if row.id}
        for trade_id in missing_ids:
            row = include_map.get(trade_id)
            if row:
                ordered_rows.append(row)

    trade_ids = [row.id for row in ordered_rows if row.id]
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


def create_trade(trade: TradeCreate, db: Session = Depends(get_db)):
    values = trade.model_dump()
    instrument = db.query(TradeInstrument).filter(
        TradeInstrument.code == (values.get("symbol") or "").strip().upper(),
        TradeInstrument.is_active == True,  # noqa: E712
    ).first()
    if instrument and values.get("instrument_type") != instrument.instrument_type:
        raise HTTPException(400, "所选品种不属于当前交易类型")
    close_time = values.get("close_time")
    close_price = values.get("close_price")
    if (close_time is None) != (close_price is None):
        raise HTTPException(400, "平仓时间和平仓价必须同时填写或同时留空")
    values["status"] = "closed" if close_time is not None else "open"
    if values["status"] == "closed":
        amount_fields = (
            ("commission_usdt", "pnl_usdt")
            if values.get("instrument_type") == "加密货币"
            else ("commission", "pnl")
        )
        if any(field not in trade.model_fields_set or values.get(field) is None for field in amount_fields):
            raise HTTPException(400, "已平仓交易必须填写手续费和盈亏金额")
    values = normalize_trade_currency_values(values)
    obj = Trade(**values, owner_role=legacy_runtime._owner_role_value_for_create())
    db.add(obj)
    db.flush()
    add_risk_point_snapshot(db, obj)
    db.commit()
    db.refresh(obj)
    return _attach_trade_view_fields(db, [obj])[0]


def get_trade(trade_id: int, db: Session = Depends(get_db)):
    row = db.query(Trade).filter(Trade.id == trade_id, Trade.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Trade not found")
    return _attach_trade_view_fields(db, [row])[0]


def update_trade(trade_id: int, data: TradeUpdate, db: Session = Depends(get_db)):
    row = db.query(Trade).filter(Trade.id == trade_id, Trade.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Trade not found")
    updates = data.model_dump(exclude_unset=True)
    next_symbol = updates.get("symbol", row.symbol)
    instrument = db.query(TradeInstrument).filter(
        TradeInstrument.code == (next_symbol or "").strip().upper(),
        TradeInstrument.is_active == True,  # noqa: E712
    ).first()
    next_instrument_type = updates.get("instrument_type", row.instrument_type)
    if instrument and next_instrument_type != instrument.instrument_type:
        raise HTTPException(400, "所选品种不属于当前交易类型")
    updates = normalize_trade_currency_values(updates, current=row)
    if updates.get("open_time") is not None:
        updates["trade_date"] = updates["open_time"].date()
    next_close_time = updates.get("close_time", row.close_time)
    next_close_price = updates.get("close_price", row.close_price)
    if (next_close_time is None) != (next_close_price is None):
        raise HTTPException(400, "平仓时间和平仓价必须同时填写或同时留空")
    updates["status"] = "closed" if next_close_time is not None else "open"
    if updates["status"] == "closed":
        if next_instrument_type == "加密货币":
            amount_values = (
                updates.get("commission_usdt", row.commission_usdt),
                updates.get("pnl_usdt", row.pnl_usdt),
            )
        else:
            amount_values = (
                updates.get("commission", row.commission),
                updates.get("pnl", row.pnl),
            )
        if any(value is None for value in amount_values):
            raise HTTPException(400, "已平仓交易必须填写手续费和盈亏金额")
    tracked_fields = ("stop_loss_point", "target_point", "capital_percentage")
    for field in tracked_fields:
        if field in updates and updates[field] is None:
            raise HTTPException(400, f"{field} cannot be null")
    next_stop_loss_point = updates.get("stop_loss_point", row.stop_loss_point)
    next_target_point = updates.get("target_point", row.target_point)
    next_capital_percentage = updates.get("capital_percentage", row.capital_percentage)
    tracked_values_touched = any(field in updates for field in tracked_fields)
    if tracked_values_touched and any(
        value is None for value in (next_stop_loss_point, next_target_point, next_capital_percentage)
    ):
        raise HTTPException(400, "stop_loss_point, target_point and capital_percentage are all required")
    should_record_risk_points = tracked_trade_values_changed(
        row,
        stop_loss_point=next_stop_loss_point,
        target_point=next_target_point,
        capital_percentage=next_capital_percentage,
    )
    for key, value in updates.items():
        setattr(row, key, value)
    if should_record_risk_points:
        add_risk_point_snapshot(db, row)
    db.commit()
    db.refresh(row)
    return _attach_trade_view_fields(db, [row])[0]


def delete_trade(trade_id: int, db: Session = Depends(get_db)):
    row = db.query(Trade).filter(Trade.id == trade_id, Trade.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Trade not found")
    row.is_deleted = True
    row.deleted_at = datetime.now()
    db.commit()
    return {"ok": True}


def list_trade_sources(owner_role: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Trade).filter(Trade.is_deleted == False)  # noqa: E712
    role_filter = legacy_runtime._owner_role_filter_for_admin(Trade, owner_role)
    if role_filter is not None:
        query = query.filter(role_filter)
    rows = query.all()
    values = {str(getattr(row, "source_display", "")).strip() for row in _attach_trade_view_fields(db, rows)}
    return {"items": sorted(value for value in values if value)}


def list_trade_symbols(owner_role: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Trade.symbol).filter(Trade.is_deleted == False, Trade.symbol.isnot(None))  # noqa: E712
    role_filter = legacy_runtime._owner_role_filter_for_admin(Trade, owner_role)
    if role_filter is not None:
        query = query.filter(role_filter)
    rows = query.distinct().order_by(Trade.symbol.asc()).all()
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
    previous_research_notes = review.research_notes if review else None
    if not review:
        review = TradeReview(trade_id=trade_id)
        db.add(review)

    payload = data.model_dump(exclude_unset=True)
    tags_raw = payload.pop("tags", None) if "tags" in payload else None
    legacy_tags_raw = payload.get("review_tags") if "review_tags" in payload else None
    for key, value in payload.items():
        setattr(review, key, value)

    if tags_raw is not None or legacy_tags_raw is not None:
        tag_names = _normalize_tag_list(tags_raw if tags_raw is not None else legacy_tags_raw)
        review.review_tags = _serialize_legacy_tags(tag_names)
        db.flush()
        _sync_trade_review_tags(db, review.id, tag_names)

    db.commit()
    db.refresh(review)
    cleanup_unreferenced_uploads(db, previous_research_notes)
    return _attach_trade_review_tags(db, [review])[0]


def delete_trade_review(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(Trade).filter(Trade.id == trade_id, Trade.is_deleted == False).first()  # noqa: E712
    if not trade:
        raise HTTPException(404, "Trade not found")
    review = db.query(TradeReview).filter(TradeReview.trade_id == trade_id).first()
    if not review:
        return {"ok": True}
    previous_research_notes = review.research_notes
    db.delete(review)
    db.commit()
    cleanup_unreferenced_uploads(db, previous_research_notes)
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
            parser_version=row.parser_version,
            created_at=row.created_at,
            updated_at=row.updated_at,
            exists_in_db=True,
        )

    return TradeSourceMetadataResponse(
        trade_id=trade_id,
        broker_name=None,
        source_label=None,
        import_channel=None,
        parser_version=None,
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

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return TradeSourceMetadataResponse(
        id=row.id,
        trade_id=row.trade_id,
        broker_name=row.broker_name,
        source_label=row.source_label,
        import_channel=row.import_channel,
        parser_version=row.parser_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
        exists_in_db=True,
    )


def get_trade_linked_plans(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(Trade).filter(Trade.id == trade_id, Trade.is_deleted == False).first()  # noqa: E712
    if not trade:
        raise HTTPException(404, "Trade not found")
    links = (
        db.query(TradePlanTradeLink)
        .filter(TradePlanTradeLink.trade_id == trade_id)
        .all()
    )
    plan_ids = [link.trade_plan_id for link in links]
    if not plan_ids:
        return []
    plans = (
        db.query(TradePlan)
        .filter(TradePlan.id.in_(plan_ids), TradePlan.is_deleted == False)  # noqa: E712
        .all()
    )
    return [
        {
            "id": p.id,
            "title": p.title,
            "plan_date": str(p.plan_date) if p.plan_date else None,
            "status": p.status,
            "symbol": p.symbol,
            "contract": p.contract,
            "direction_bias": p.direction_bias,
            "setup_type": p.setup_type,
            "entry_zone": p.entry_zone,
            "stop_loss_plan": p.stop_loss_plan,
            "target_plan": p.target_plan,
            "invalid_condition": p.invalid_condition,
            "thesis": p.thesis,
            "risk_notes": p.risk_notes,
            "execution_checklist": p.execution_checklist,
            "priority": p.priority,
        }
        for p in plans
    ]
