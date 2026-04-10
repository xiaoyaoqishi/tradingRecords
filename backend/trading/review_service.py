from typing import Any, Dict, List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import Review, ReviewTradeLink, Trade, TradeSourceMetadata
from trading.source_service import resolve_trade_source_fields


REVIEW_SCOPE_VALUES = {
    "periodic",
    "themed",
    "campaign",
    "custom",
}

REVIEW_LINK_ROLE_VALUES = {
    "linked_trade",
    "best_trade",
    "worst_trade",
    "representative_trade",
}


def normalize_review_scope(value: Any) -> str:
    scope = str(value or "periodic").strip() or "periodic"
    if scope not in REVIEW_SCOPE_VALUES:
        return "custom"
    return scope


def normalize_review_link_role(value: Any) -> str:
    role = str(value or "linked_trade").strip() or "linked_trade"
    if role not in REVIEW_LINK_ROLE_VALUES:
        return "linked_trade"
    return role


def attach_review_link_fields(db: Session, rows: List[Review]) -> List[Review]:
    if not rows:
        return rows
    review_ids = [r.id for r in rows if r.id]
    if not review_ids:
        return rows
    link_rows = (
        db.query(ReviewTradeLink)
        .filter(ReviewTradeLink.review_id.in_(review_ids))
        .order_by(ReviewTradeLink.review_id.asc(), ReviewTradeLink.id.asc())
        .all()
    )
    grouped: Dict[int, List[ReviewTradeLink]] = {}
    for link in link_rows:
        grouped.setdefault(link.review_id, []).append(link)
    trade_ids = list({link.trade_id for link in link_rows if link.trade_id})
    trade_by_id: Dict[int, Trade] = {}
    metadata_by_trade_id: Dict[int, TradeSourceMetadata] = {}
    if trade_ids:
        trade_rows = db.query(Trade).filter(Trade.id.in_(trade_ids)).all()
        trade_by_id = {t.id: t for t in trade_rows}
        metadata_rows = db.query(TradeSourceMetadata).filter(TradeSourceMetadata.trade_id.in_(trade_ids)).all()
        metadata_by_trade_id = {m.trade_id: m for m in metadata_rows}
    for row in rows:
        links = grouped.get(row.id, [])
        for link in links:
            trade = trade_by_id.get(link.trade_id)
            if not trade:
                setattr(link, "trade_summary", None)
                continue
            source_fields = resolve_trade_source_fields(trade, metadata_by_trade_id.get(trade.id))
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
                },
            )
        setattr(row, "trade_links", links)
        setattr(row, "linked_trade_ids", [x.trade_id for x in links])
    return rows


def sync_review_trade_links(db: Session, review: Review, links: List[Dict[str, Any]]) -> None:
    db.query(ReviewTradeLink).filter(ReviewTradeLink.review_id == review.id).delete()
    if not links:
        return

    # 按 trade_id 去重，后出现的条目覆盖前面的 role/notes。
    deduped_by_trade_id: Dict[int, Dict[str, Any]] = {}
    for item in links:
        trade_id = int(item.get("trade_id") or 0)
        if trade_id <= 0:
            continue
        deduped_by_trade_id[trade_id] = {
            "trade_id": trade_id,
            "role": normalize_review_link_role(item.get("role")),
            "notes": item.get("notes"),
        }
    final_links = list(deduped_by_trade_id.values())
    if not final_links:
        return

    requested_trade_ids = [x["trade_id"] for x in final_links]
    existing_trade_ids = {
        trade_id for (trade_id,) in db.query(Trade.id).filter(Trade.id.in_(requested_trade_ids)).all()
    }
    missing = [str(tid) for tid in requested_trade_ids if tid not in existing_trade_ids]
    if missing:
        raise HTTPException(400, f"trade_id 不存在: {', '.join(missing)}")

    for item in final_links:
        db.add(
            ReviewTradeLink(
                review_id=review.id,
                trade_id=item["trade_id"],
                role=item["role"],
                notes=item.get("notes"),
            )
        )
