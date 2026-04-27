from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.db import get_db
from models import TradePlan
from schemas import (
    TradePlanCreate,
    TradePlanReviewSessionLinksPayload,
    TradePlanTradeLinksPayload,
    TradePlanUpdate,
)
from services import review_runtime
from services import runtime as legacy_runtime
from trading.trade_plan_service import (
    assert_trade_plan_status_transition as _trade_plan_assert_status_transition,
    attach_trade_plan_link_fields as _trade_plan_attach_link_fields,
    normalize_trade_plan_status as _trade_plan_normalize_status,
    sync_trade_plan_review_session_links as _trade_plan_sync_review_session_links,
    sync_trade_plan_trade_links as _trade_plan_sync_trade_links,
)
from trading.tag_service import normalize_tag_list as _normalize_tag_list
from trading.tag_service import serialize_legacy_tags as _serialize_legacy_tags


def _attach_trade_plan_fields(db: Session, rows: List[TradePlan]) -> List[TradePlan]:
    rows = _trade_plan_attach_link_fields(db, rows)
    for row in rows:
        setattr(row, "tags", review_runtime._parse_tags_text(row.tags_text))
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
    role_filter = legacy_runtime._owner_role_filter_for_admin(TradePlan, owner_role)
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
    obj = TradePlan(**data, owner_role=legacy_runtime._owner_role_value_for_create())
    db.add(obj)
    db.flush()
    obj.tags_text = _serialize_legacy_tags(_normalize_tag_list(tags_raw))
    _trade_plan_sync_trade_links(db, obj, [item.model_dump() for item in (payload.trade_links or [])])
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
    for key, value in updates.items():
        setattr(row, key, value)
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
    _trade_plan_sync_trade_links(db, row, [item.model_dump() for item in (payload.trade_links or [])])
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
    _trade_plan_sync_review_session_links(
        db,
        row,
        [item.model_dump() for item in (payload.review_session_links or [])],
    )
    db.commit()
    db.refresh(row)
    return _attach_trade_plan_fields(db, [row])[0]


def create_followup_review_session_from_trade_plan(trade_plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(TradePlan).filter(TradePlan.id == trade_plan_id, TradePlan.is_deleted == False).first()  # noqa: E712
    if not plan:
        raise HTTPException(404, "Trade plan not found")
    plan = _attach_trade_plan_fields(db, [plan])[0]
    trade_links = [
        {"trade_id": item.trade_id, "role": "linked_trade", "sort_order": index}
        for index, item in enumerate(getattr(plan, "trade_links", []))
    ]
    session = review_runtime._create_review_session_from_payload(
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
            "tags": review_runtime._parse_tags_text(plan.tags_text),
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
