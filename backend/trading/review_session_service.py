from typing import Any, Dict, List

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from core.errors import AppError
from models import ReviewSession, ReviewSessionTradeLink, Trade, TradeReview, TradeSourceMetadata
from trading.source_service import resolve_trade_source_fields


REVIEW_SESSION_SCOPE_VALUES = {
    "periodic",
    "themed",
    "campaign",
    "custom",
}

REVIEW_SESSION_KIND_VALUES = {
    "period",
    "theme",
    "setup",
    "symbol",
    "regime",
    "failure-pattern",
    "source",
    "plan-followup",
    "custom",
}

REVIEW_SELECTION_MODE_VALUES = {
    "manual",
    "filter_snapshot",
    "saved_cohort",
    "plan_linked",
    "imported",
}

REVIEW_SELECTION_TARGET_VALUES = {
    "full_filtered",
    "current_page",
}

REVIEW_SESSION_LINK_ROLE_VALUES = {
    "linked_trade",
    "best_trade",
    "worst_trade",
    "representative_trade",
    "outlier_trade",
    "execution_mistake_example",
    "setup_example",
}


def normalize_review_session_scope(value: Any) -> str:
    scope = str(value or "custom").strip() or "custom"
    if scope not in REVIEW_SESSION_SCOPE_VALUES:
        return "custom"
    return scope


def normalize_review_session_kind(value: Any) -> str:
    kind = str(value or "custom").strip() or "custom"
    if kind not in REVIEW_SESSION_KIND_VALUES:
        return "custom"
    return kind


def normalize_review_selection_mode(value: Any) -> str:
    mode = str(value or "manual").strip() or "manual"
    if mode not in REVIEW_SELECTION_MODE_VALUES:
        return "manual"
    return mode


def normalize_review_selection_target(value: Any) -> str:
    target = str(value or "full_filtered").strip() or "full_filtered"
    if target not in REVIEW_SELECTION_TARGET_VALUES:
        return "full_filtered"
    return target


def normalize_review_session_link_role(value: Any) -> str:
    role = str(value or "linked_trade").strip() or "linked_trade"
    if role not in REVIEW_SESSION_LINK_ROLE_VALUES:
        return "linked_trade"
    return role


def attach_review_session_link_fields(db: Session, rows: List[ReviewSession]) -> List[ReviewSession]:
    if not rows:
        return rows
    review_session_ids = [r.id for r in rows if r.id]
    if not review_session_ids:
        return rows
    try:
        link_rows = (
            db.query(ReviewSessionTradeLink)
            .filter(ReviewSessionTradeLink.review_session_id.in_(review_session_ids))
            .order_by(ReviewSessionTradeLink.review_session_id.asc(), ReviewSessionTradeLink.sort_order.asc(), ReviewSessionTradeLink.id.asc())
            .all()
        )
    except OperationalError:
        link_rows = []
    grouped: Dict[int, List[ReviewSessionTradeLink]] = {}
    for link in link_rows:
        grouped.setdefault(link.review_session_id, []).append(link)
    trade_ids = list({link.trade_id for link in link_rows if link.trade_id})
    trade_by_id: Dict[int, Trade] = {}
    metadata_by_trade_id: Dict[int, TradeSourceMetadata] = {}
    review_by_trade_id: Dict[int, TradeReview] = {}
    if trade_ids:
        trade_rows = (
            db.query(Trade)
            .filter(Trade.id.in_(trade_ids), Trade.is_deleted == False)  # noqa: E712
            .all()
        )
        trade_by_id = {t.id: t for t in trade_rows}
        metadata_rows = db.query(TradeSourceMetadata).filter(TradeSourceMetadata.trade_id.in_(trade_ids)).all()
        metadata_by_trade_id = {m.trade_id: m for m in metadata_rows}
        review_rows = db.query(TradeReview).filter(TradeReview.trade_id.in_(trade_ids)).all()
        review_by_trade_id = {x.trade_id: x for x in review_rows}
    for row in rows:
        links = grouped.get(row.id, [])
        for link in links:
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
        setattr(row, "trade_links", links)
        setattr(row, "linked_trade_ids", [x.trade_id for x in links])
    return rows


def sync_review_session_trade_links(db: Session, review_session: ReviewSession, links: List[Dict[str, Any]]) -> None:
    db.query(ReviewSessionTradeLink).filter(ReviewSessionTradeLink.review_session_id == review_session.id).delete()
    if not links:
        return

    deduped_by_trade_id: Dict[int, Dict[str, Any]] = {}
    for item in links:
        trade_id = int(item.get("trade_id") or 0)
        if trade_id <= 0:
            continue
        deduped_by_trade_id[trade_id] = {
            "trade_id": trade_id,
            "role": normalize_review_session_link_role(item.get("role")),
            "note": item.get("note") or item.get("notes"),
            "sort_order": int(item.get("sort_order") or 0),
        }
    final_links = list(deduped_by_trade_id.values())
    final_links.sort(key=lambda x: (x["sort_order"], x["trade_id"]))
    if not final_links:
        return

    requested_trade_ids = [x["trade_id"] for x in final_links]
    existing_trade_ids = {
        trade_id
        for (trade_id,) in (
            db.query(Trade.id)
            .filter(Trade.id.in_(requested_trade_ids), Trade.is_deleted == False)  # noqa: E712
            .all()
        )
    }
    missing = [str(tid) for tid in requested_trade_ids if tid not in existing_trade_ids]
    if missing:
        raise AppError("invalid_trade_id", f"trade_id not found: {', '.join(missing)}", status_code=400)

    for item in final_links:
        db.add(
            ReviewSessionTradeLink(
                review_session_id=review_session.id,
                trade_id=item["trade_id"],
                role=item["role"],
                note=item.get("note"),
                sort_order=item.get("sort_order") or 0,
            )
        )
