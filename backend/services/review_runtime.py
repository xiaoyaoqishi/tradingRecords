from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.db import get_db
from models import ReviewSession, Trade
from schemas import (
    ReviewCreate,
    ReviewSessionCreate,
    ReviewSessionCreateFromSelection,
    ReviewSessionTradeLinksPayload,
    ReviewSessionUpdate,
    ReviewTradeLinksPayload,
    ReviewUpdate,
)
from services import runtime as legacy_runtime
from trading.review_session_service import (
    attach_review_session_link_fields as _review_session_attach_link_fields,
    normalize_review_selection_mode as _review_session_normalize_selection_mode,
    normalize_review_selection_target as _review_session_normalize_selection_target,
    normalize_review_session_kind as _review_session_normalize_kind,
    normalize_review_session_scope as _review_session_normalize_scope,
    sync_review_session_trade_links as _review_session_sync_trade_links,
)
from trading.source_service import apply_source_keyword_filter as _source_apply_source_keyword_filter
from trading.tag_service import normalize_tag_list as _normalize_tag_list
from trading.tag_service import serialize_legacy_tags as _serialize_legacy_tags


def _parse_tags_text(tags_text: Optional[str]) -> List[str]:
    return _normalize_tag_list(tags_text)


def _attach_review_session_fields(db: Session, rows: List[ReviewSession]) -> List[ReviewSession]:
    rows = _review_session_attach_link_fields(db, rows)
    for row in rows:
        setattr(row, "tags", _parse_tags_text(row.tags_text))
    return rows


def _review_session_to_legacy_response(row: ReviewSession) -> Dict[str, Any]:
    review_date = row.created_at.date() if row.created_at else date.today()
    scope = row.review_scope or "custom"
    review_type = "weekly" if scope == "periodic" else "custom"
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
                "id": item.id,
                "review_id": row.id,
                "trade_id": item.trade_id,
                "role": item.role,
                "notes": item.note,
                "trade_summary": getattr(item, "trade_summary", None),
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            for item in getattr(row, "trade_links", [])
        ],
        "linked_trade_ids": [item.trade_id for item in getattr(row, "trade_links", [])],
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
    role_filter = legacy_runtime._owner_role_filter_for_admin(Trade, owner_role)
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
    return _source_apply_source_keyword_filter(q, source_keyword)


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
    return [row.id for row in rows if row.id]


def _create_review_session_from_payload(
    db: Session,
    payload: Dict[str, Any],
    trade_links: List[Dict[str, Any]],
) -> ReviewSession:
    tags_raw = payload.pop("tags", None) if "tags" in payload else None
    payload["review_kind"] = _review_session_normalize_kind(payload.get("review_kind"))
    payload["review_scope"] = _review_session_normalize_scope(payload.get("review_scope"))
    payload["selection_mode"] = _review_session_normalize_selection_mode(payload.get("selection_mode"))
    payload["owner_role"] = payload.get("owner_role") or legacy_runtime._owner_role_value_for_create()
    obj = ReviewSession(**payload)
    db.add(obj)
    db.flush()
    obj.tags_text = _serialize_legacy_tags(_normalize_tag_list(tags_raw))
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
    role_filter = legacy_runtime._owner_role_filter_for_admin(ReviewSession, owner_role)
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
    return _create_review_session_from_payload(
        db,
        payload.model_dump(exclude={"trade_links"}),
        [item.model_dump() for item in (payload.trade_links or [])],
    )


def create_review_session_from_selection(
    payload: ReviewSessionCreateFromSelection,
    db: Session = Depends(get_db),
):
    selection_target = _review_session_normalize_selection_target(payload.selection_target)
    selection_mode = _review_session_normalize_selection_mode(payload.selection_mode)

    if selection_mode == "manual":
        trade_ids = [int(item) for item in payload.trade_ids if int(item) > 0]
    elif selection_mode == "filter_snapshot":
        if selection_target == "current_page":
            trade_ids = [int(item) for item in payload.trade_ids if int(item) > 0]
        else:
            trade_ids = _build_trade_ids_from_filter(db, payload.filter_params or {})
    else:
        trade_ids = [int(item) for item in payload.trade_ids if int(item) > 0]

    dedup_ids: List[int] = []
    seen = set()
    for trade_id in trade_ids:
        if trade_id in seen:
            continue
        seen.add(trade_id)
        dedup_ids.append(trade_id)

    trade_links = [
        {"trade_id": trade_id, "role": "linked_trade", "sort_order": index}
        for index, trade_id in enumerate(dedup_ids)
    ]
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

    return _create_review_session_from_payload(
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


def get_review_session(review_session_id: int, db: Session = Depends(get_db)):
    row = (
        db.query(ReviewSession)
        .filter(ReviewSession.id == review_session_id, ReviewSession.is_deleted == False)  # noqa: E712
        .first()
    )
    if not row:
        raise HTTPException(404, "Review session not found")
    return _attach_review_session_fields(db, [row])[0]


def update_review_session(review_session_id: int, data: ReviewSessionUpdate, db: Session = Depends(get_db)):
    row = (
        db.query(ReviewSession)
        .filter(ReviewSession.id == review_session_id, ReviewSession.is_deleted == False)  # noqa: E712
        .first()
    )
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
    for key, value in payload.items():
        setattr(row, key, value)
    if tags_raw is not None:
        row.tags_text = _serialize_legacy_tags(_normalize_tag_list(tags_raw))
    db.commit()
    db.refresh(row)
    return _attach_review_session_fields(db, [row])[0]


def delete_review_session(review_session_id: int, db: Session = Depends(get_db)):
    row = (
        db.query(ReviewSession)
        .filter(ReviewSession.id == review_session_id, ReviewSession.is_deleted == False)  # noqa: E712
        .first()
    )
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
    row = (
        db.query(ReviewSession)
        .filter(ReviewSession.id == review_session_id, ReviewSession.is_deleted == False)  # noqa: E712
        .first()
    )
    if not row:
        raise HTTPException(404, "Review session not found")
    _review_session_sync_trade_links(db, row, [item.model_dump() for item in (payload.trade_links or [])])
    db.commit()
    db.refresh(row)
    return _attach_review_session_fields(db, [row])[0]


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
    kind = kind_map.get(review_type) if review_type else None
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
        filtered_rows = []
        for row in rows:
            row_date = row.created_at.date() if row.created_at else date.today()
            if date_from and str(row_date) < str(date_from):
                continue
            if date_to and str(row_date) > str(date_to):
                continue
            filtered_rows.append(row)
        rows = filtered_rows
    return [_review_session_to_legacy_response(row) for row in rows]


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
    for key, value in mapped.items():
        if value is None:
            continue
        if key == "review_scope":
            setattr(row, key, _review_session_normalize_scope(value))
        else:
            setattr(row, key, value)
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
        [{"trade_id": item.trade_id, "role": item.role, "note": item.notes} for item in (payload.trade_links or [])],
    )
    db.commit()
    db.refresh(row)
    row = _attach_review_session_fields(db, [row])[0]
    return _review_session_to_legacy_response(row)
