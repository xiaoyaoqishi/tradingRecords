import re
from typing import Dict, Iterable, List, Optional, Sequence, Union

from sqlalchemy.orm import Session

from models import (
    KnowledgeItem,
    KnowledgeItemTagLink,
    Review,
    ReviewTagLink,
    TagTerm,
    TradeReview,
    TradeReviewTagLink,
)

TagRaw = Optional[Union[str, Sequence[str]]]


def _tag_key(name: str) -> str:
    return name.strip().lower()


def normalize_tag_list(raw: TagRaw) -> List[str]:
    if raw is None:
        return []
    values: List[str] = []
    if isinstance(raw, str):
        parts = re.split(r"[,\n;|，、]+", raw)
        values.extend(parts)
    else:
        for item in raw:
            values.append(str(item or ""))
    out: List[str] = []
    seen = set()
    for item in values:
        name = str(item or "").strip()
        if not name:
            continue
        key = _tag_key(name)
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def serialize_legacy_tags(tags: Iterable[str]) -> Optional[str]:
    values = [str(x).strip() for x in tags if str(x).strip()]
    if not values:
        return None
    return ",".join(values)


def _ensure_tag_terms(db: Session, names: List[str]) -> Dict[str, TagTerm]:
    if not names:
        return {}
    keys = [_tag_key(x) for x in names]
    existed_rows = db.query(TagTerm).filter(TagTerm.name_key.in_(keys)).all()
    by_key = {x.name_key: x for x in existed_rows}
    for name in names:
        key = _tag_key(name)
        if key in by_key:
            continue
        row = TagTerm(name=name, name_key=key)
        db.add(row)
        db.flush()
        by_key[key] = row
    return by_key


def _sync_entity_links(
    db: Session,
    *,
    names: List[str],
    delete_query,
    link_cls,
    fk_field: str,
    fk_value: int,
):
    delete_query.delete()
    if not names:
        return
    terms = _ensure_tag_terms(db, names)
    for name in names:
        key = _tag_key(name)
        term = terms[key]
        payload = {
            fk_field: fk_value,
            "tag_term_id": term.id,
        }
        db.add(link_cls(**payload))


def sync_trade_review_tags(db: Session, trade_review_id: int, names: List[str]) -> None:
    _sync_entity_links(
        db,
        names=names,
        delete_query=db.query(TradeReviewTagLink).filter(TradeReviewTagLink.trade_review_id == trade_review_id),
        link_cls=TradeReviewTagLink,
        fk_field="trade_review_id",
        fk_value=trade_review_id,
    )


def sync_review_tags(db: Session, review_id: int, names: List[str]) -> None:
    _sync_entity_links(
        db,
        names=names,
        delete_query=db.query(ReviewTagLink).filter(ReviewTagLink.review_id == review_id),
        link_cls=ReviewTagLink,
        fk_field="review_id",
        fk_value=review_id,
    )


def sync_knowledge_item_tags(db: Session, knowledge_item_id: int, names: List[str]) -> None:
    _sync_entity_links(
        db,
        names=names,
        delete_query=db.query(KnowledgeItemTagLink).filter(KnowledgeItemTagLink.knowledge_item_id == knowledge_item_id),
        link_cls=KnowledgeItemTagLink,
        fk_field="knowledge_item_id",
        fk_value=knowledge_item_id,
    )


def _attach_tags_generic(
    db: Session,
    *,
    rows,
    row_id_attr: str,
    link_cls,
    link_fk_field: str,
    fallback_text_attr: str,
):
    if not rows:
        return rows
    ids = [getattr(x, row_id_attr) for x in rows if getattr(x, row_id_attr, None)]
    if not ids:
        return rows
    link_rows = db.query(link_cls).filter(getattr(link_cls, link_fk_field).in_(ids)).all()
    term_ids = [x.tag_term_id for x in link_rows]
    terms = {}
    if term_ids:
        terms = {x.id: x for x in db.query(TagTerm).filter(TagTerm.id.in_(term_ids)).all()}
    grouped: Dict[int, List[str]] = {}
    for link in link_rows:
        row_id = getattr(link, link_fk_field)
        term = terms.get(link.tag_term_id)
        if not term:
            continue
        grouped.setdefault(row_id, []).append(term.name)
    for row in rows:
        row_id = getattr(row, row_id_attr)
        tags = grouped.get(row_id, [])
        if not tags:
            tags = normalize_tag_list(getattr(row, fallback_text_attr, None))
        setattr(row, "tags", tags)
    return rows


def attach_trade_review_tags(db: Session, rows: List[TradeReview]) -> List[TradeReview]:
    return _attach_tags_generic(
        db,
        rows=rows,
        row_id_attr="id",
        link_cls=TradeReviewTagLink,
        link_fk_field="trade_review_id",
        fallback_text_attr="review_tags",
    )


def attach_review_tags(db: Session, rows: List[Review]) -> List[Review]:
    return _attach_tags_generic(
        db,
        rows=rows,
        row_id_attr="id",
        link_cls=ReviewTagLink,
        link_fk_field="review_id",
        fallback_text_attr="tags_text",
    )


def attach_knowledge_item_tags(db: Session, rows: List[KnowledgeItem]) -> List[KnowledgeItem]:
    return _attach_tags_generic(
        db,
        rows=rows,
        row_id_attr="id",
        link_cls=KnowledgeItemTagLink,
        link_fk_field="knowledge_item_id",
        fallback_text_attr="tags_text",
    )
