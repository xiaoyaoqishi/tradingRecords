from typing import Any, Dict, List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import (
    ReviewSession,
    Trade,
    TradePlan,
    TradePlanReviewSessionLink,
    TradePlanTradeLink,
    TradeReview,
    TradeSourceMetadata,
)
from trading.source_service import resolve_trade_source_fields


TRADE_PLAN_STATUS_VALUES = {
    "draft",
    "active",
    "triggered",
    "executed",
    "cancelled",
    "expired",
    "reviewed",
}

TRADE_PLAN_TRANSITIONS = {
    "draft": {"active"},
    "active": {"triggered", "cancelled", "expired"},
    "triggered": {"executed", "cancelled"},
    "executed": {"reviewed"},
    "cancelled": set(),
    "expired": set(),
    "reviewed": set(),
}


def normalize_trade_plan_status(value: Any) -> str:
    status = str(value or "draft").strip() or "draft"
    if status not in TRADE_PLAN_STATUS_VALUES:
        raise HTTPException(400, f"invalid trade plan status: {status}")
    return status


def assert_trade_plan_status_transition(current_status: str, next_status: str) -> None:
    current = normalize_trade_plan_status(current_status)
    target = normalize_trade_plan_status(next_status)
    if current == target:
        return
    if target not in TRADE_PLAN_TRANSITIONS.get(current, set()):
        raise HTTPException(400, f"invalid status transition: {current} -> {target}")


def attach_trade_plan_link_fields(db: Session, rows: List[TradePlan]) -> List[TradePlan]:
    if not rows:
        return rows

    plan_ids = [r.id for r in rows if r.id]
    if not plan_ids:
        return rows

    trade_link_rows = (
        db.query(TradePlanTradeLink)
        .filter(TradePlanTradeLink.trade_plan_id.in_(plan_ids))
        .order_by(TradePlanTradeLink.trade_plan_id.asc(), TradePlanTradeLink.sort_order.asc(), TradePlanTradeLink.id.asc())
        .all()
    )
    review_session_link_rows = (
        db.query(TradePlanReviewSessionLink)
        .filter(TradePlanReviewSessionLink.trade_plan_id.in_(plan_ids))
        .order_by(TradePlanReviewSessionLink.trade_plan_id.asc(), TradePlanReviewSessionLink.id.asc())
        .all()
    )

    trade_grouped: Dict[int, List[TradePlanTradeLink]] = {}
    for link in trade_link_rows:
        trade_grouped.setdefault(link.trade_plan_id, []).append(link)

    review_grouped: Dict[int, List[TradePlanReviewSessionLink]] = {}
    for link in review_session_link_rows:
        review_grouped.setdefault(link.trade_plan_id, []).append(link)

    trade_ids = list({x.trade_id for x in trade_link_rows if x.trade_id})
    trade_by_id: Dict[int, Trade] = {}
    metadata_by_trade_id: Dict[int, TradeSourceMetadata] = {}
    review_by_trade_id: Dict[int, TradeReview] = {}
    if trade_ids:
        trade_rows = db.query(Trade).filter(Trade.id.in_(trade_ids)).all()
        trade_by_id = {t.id: t for t in trade_rows}
        metadata_rows = db.query(TradeSourceMetadata).filter(TradeSourceMetadata.trade_id.in_(trade_ids)).all()
        metadata_by_trade_id = {m.trade_id: m for m in metadata_rows}
        review_rows = db.query(TradeReview).filter(TradeReview.trade_id.in_(trade_ids)).all()
        review_by_trade_id = {x.trade_id: x for x in review_rows}

    review_session_ids = list({x.review_session_id for x in review_session_link_rows if x.review_session_id})
    review_session_by_id: Dict[int, ReviewSession] = {}
    if review_session_ids:
        review_session_rows = db.query(ReviewSession).filter(ReviewSession.id.in_(review_session_ids)).all()
        review_session_by_id = {r.id: r for r in review_session_rows}

    for row in rows:
        trade_links = trade_grouped.get(row.id, [])
        for link in trade_links:
            trade = trade_by_id.get(link.trade_id)
            if not trade:
                setattr(link, "trade_summary", None)
                continue
            source_fields = resolve_trade_source_fields(trade, metadata_by_trade_id.get(trade.id))
            trade_review = review_by_trade_id.get(trade.id)
            setattr(
                link,
                "trade_summary",
                {
                    "trade_id": trade.id,
                    "trade_date": trade.trade_date,
                    "instrument_type": trade.instrument_type,
                    "symbol": trade.symbol,
                    "contract": trade.contract,
                    "direction": trade.direction,
                    "quantity": trade.quantity,
                    "open_price": trade.open_price,
                    "close_price": trade.close_price,
                    "status": trade.status,
                    "pnl": trade.pnl,
                    "source_display": source_fields.get("source_display"),
                    "has_trade_review": bool(trade_review),
                    "review_conclusion": trade_review.review_conclusion if trade_review else None,
                },
            )

        review_session_links = review_grouped.get(row.id, [])
        for link in review_session_links:
            setattr(link, "review_session", review_session_by_id.get(link.review_session_id))

        setattr(row, "trade_links", trade_links)
        setattr(row, "linked_trade_ids", [x.trade_id for x in trade_links])
        setattr(row, "review_session_links", review_session_links)

    return rows


def sync_trade_plan_trade_links(db: Session, trade_plan: TradePlan, links: List[Dict[str, Any]]) -> None:
    db.query(TradePlanTradeLink).filter(TradePlanTradeLink.trade_plan_id == trade_plan.id).delete()
    if not links:
        return

    deduped_by_trade_id: Dict[int, Dict[str, Any]] = {}
    for item in links:
        trade_id = int(item.get("trade_id") or 0)
        if trade_id <= 0:
            continue
        deduped_by_trade_id[trade_id] = {
            "trade_id": trade_id,
            "note": item.get("note") or item.get("notes"),
            "sort_order": int(item.get("sort_order") or 0),
        }

    final_links = list(deduped_by_trade_id.values())
    final_links.sort(key=lambda x: (x["sort_order"], x["trade_id"]))
    if not final_links:
        return

    requested_trade_ids = [x["trade_id"] for x in final_links]
    existing_trade_ids = {
        trade_id for (trade_id,) in db.query(Trade.id).filter(Trade.id.in_(requested_trade_ids)).all()
    }
    missing = [str(tid) for tid in requested_trade_ids if tid not in existing_trade_ids]
    if missing:
        raise HTTPException(400, f"trade_id not found: {', '.join(missing)}")

    for item in final_links:
        db.add(
            TradePlanTradeLink(
                trade_plan_id=trade_plan.id,
                trade_id=item["trade_id"],
                note=item.get("note"),
                sort_order=item.get("sort_order") or 0,
            )
        )


def sync_trade_plan_review_session_links(db: Session, trade_plan: TradePlan, links: List[Dict[str, Any]]) -> None:
    db.query(TradePlanReviewSessionLink).filter(TradePlanReviewSessionLink.trade_plan_id == trade_plan.id).delete()
    if not links:
        return

    deduped_by_review_session_id: Dict[int, Dict[str, Any]] = {}
    for item in links:
        review_session_id = int(item.get("review_session_id") or 0)
        if review_session_id <= 0:
            continue
        deduped_by_review_session_id[review_session_id] = {
            "review_session_id": review_session_id,
            "note": item.get("note"),
        }

    final_links = list(deduped_by_review_session_id.values())
    if not final_links:
        return

    requested_ids = [x["review_session_id"] for x in final_links]
    existing_ids = {
        review_session_id
        for (review_session_id,) in db.query(ReviewSession.id).filter(ReviewSession.id.in_(requested_ids)).all()
    }
    missing = [str(tid) for tid in requested_ids if tid not in existing_ids]
    if missing:
        raise HTTPException(400, f"review_session_id not found: {', '.join(missing)}")

    for item in final_links:
        db.add(
            TradePlanReviewSessionLink(
                trade_plan_id=trade_plan.id,
                review_session_id=item["review_session_id"],
                note=item.get("note"),
            )
        )
