from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models import KnowledgeItem, KnowledgeItemNoteLink, Note


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


def normalize_related_note_ids(raw: Optional[Iterable[Any]]) -> List[int]:
    if raw is None:
        return []
    out: List[int] = []
    seen = set()
    for item in raw:
        try:
            note_id = int(item)
        except (TypeError, ValueError):
            continue
        if note_id <= 0 or note_id in seen:
            continue
        seen.add(note_id)
        out.append(note_id)
    return out


def sync_knowledge_item_note_links(db: Session, knowledge_item_id: int, note_ids: List[int]) -> None:
    valid_note_ids: set[int] = set()
    if note_ids:
        rows = (
            db.query(Note.id)
            .filter(
                Note.id.in_(note_ids),
                Note.note_type == "doc",
                Note.is_deleted == False,  # noqa: E712
            )
            .all()
        )
        valid_note_ids = {row[0] for row in rows}

    db.query(KnowledgeItemNoteLink).filter(
        KnowledgeItemNoteLink.knowledge_item_id == knowledge_item_id
    ).delete(synchronize_session=False)

    for idx, note_id in enumerate(note_ids):
        if note_id not in valid_note_ids:
            continue
        db.add(
            KnowledgeItemNoteLink(
                knowledge_item_id=knowledge_item_id,
                note_id=note_id,
                sort_order=idx,
            )
        )


def attach_knowledge_item_related_notes(db: Session, rows: List[KnowledgeItem]) -> List[KnowledgeItem]:
    if not rows:
        return rows
    item_ids = [row.id for row in rows if getattr(row, "id", None)]
    if not item_ids:
        return rows

    link_rows = (
        db.query(KnowledgeItemNoteLink)
        .filter(KnowledgeItemNoteLink.knowledge_item_id.in_(item_ids))
        .order_by(
            KnowledgeItemNoteLink.knowledge_item_id.asc(),
            KnowledgeItemNoteLink.sort_order.asc(),
            KnowledgeItemNoteLink.id.asc(),
        )
        .all()
    )
    note_ids = [link.note_id for link in link_rows]
    note_map: Dict[int, Note] = {}
    if note_ids:
        notes = (
            db.query(Note)
            .filter(
                Note.id.in_(note_ids),
                Note.note_type == "doc",
                Note.is_deleted == False,  # noqa: E712
            )
            .all()
        )
        note_map = {note.id: note for note in notes}

    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for link in link_rows:
        note = note_map.get(link.note_id)
        if not note:
            continue
        grouped.setdefault(link.knowledge_item_id, []).append(
            {
                "id": note.id,
                "title": (note.title or "").strip() or "无标题",
                "note_type": note.note_type,
                "updated_at": str(note.updated_at) if note.updated_at else None,
                "notebook_id": note.notebook_id,
            }
        )

    for row in rows:
        related_notes = grouped.get(row.id, [])
        setattr(row, "related_notes", related_notes)
        setattr(row, "related_note_ids", [item["id"] for item in related_notes])
    return rows
