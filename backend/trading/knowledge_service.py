from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models import KnowledgeItem


KNOWLEDGE_CATEGORY_VALUES = [
    "broker_reference",
    "symbol_note",
    "pattern_dictionary",
    "regime_note",
    "strategy_playbook",
    "execution_checklist",
    "review_heuristic",
    "risk_rule",
    "infrastructure_note",
]


def normalize_knowledge_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str):
            trimmed = value.strip()
            out[key] = trimmed or None
        else:
            out[key] = value
    if out.get("category") is None:
        out["category"] = "pattern_dictionary"
    if out.get("status") is None:
        out["status"] = "active"
    if out.get("priority") is None:
        out["priority"] = "medium"
    return out


def list_knowledge_items(
    db: Session,
    *,
    category: Optional[str],
    status: Optional[str],
    tag: Optional[str],
    keyword: Optional[str],
    page: int,
    size: int,
) -> List[KnowledgeItem]:
    query = db.query(KnowledgeItem)
    if category:
        query = query.filter(KnowledgeItem.category == category)
    if status:
        query = query.filter(KnowledgeItem.status == status)
    if tag and tag.strip():
        query = query.filter(KnowledgeItem.tags_text.contains(tag.strip()))
    if keyword and keyword.strip():
        kw = keyword.strip()
        query = query.filter(
            or_(
                KnowledgeItem.title.contains(kw),
                KnowledgeItem.summary.contains(kw),
                KnowledgeItem.content.contains(kw),
                KnowledgeItem.tags_text.contains(kw),
                KnowledgeItem.related_symbol.contains(kw),
                KnowledgeItem.related_pattern.contains(kw),
                KnowledgeItem.related_regime.contains(kw),
            )
        )
    return (
        query.order_by(KnowledgeItem.updated_at.desc(), KnowledgeItem.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )


def list_knowledge_categories(db: Session) -> List[str]:
    values = set(KNOWLEDGE_CATEGORY_VALUES)
    rows = db.query(KnowledgeItem.category).filter(KnowledgeItem.category.isnot(None)).all()
    for (category,) in rows:
        if category and str(category).strip():
            values.add(str(category).strip())
    return sorted(values)
