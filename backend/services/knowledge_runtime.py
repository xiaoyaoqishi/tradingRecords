from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.db import get_db
from models import KnowledgeCategory, KnowledgeItem
from schemas import KnowledgeItemCreate, KnowledgeItemUpdate
from services import runtime as legacy_runtime
from trading.knowledge_service import (
    attach_knowledge_item_related_notes as _knowledge_attach_related_notes,
    create_knowledge_category as _knowledge_create_category,
    delete_knowledge_category as _knowledge_delete_category,
    list_knowledge_categories as _knowledge_list_categories,
    list_knowledge_items as _knowledge_list_knowledge_items,
    normalize_knowledge_category_name as _knowledge_normalize_category_name,
    normalize_knowledge_payload as _knowledge_normalize_payload,
    normalize_related_note_ids as _knowledge_normalize_related_note_ids,
    sync_knowledge_item_note_links as _knowledge_sync_note_links,
)
from trading.tag_service import attach_knowledge_item_tags as _attach_knowledge_item_tags
from trading.tag_service import normalize_tag_list as _normalize_tag_list
from trading.tag_service import serialize_legacy_tags as _serialize_legacy_tags
from trading.tag_service import sync_knowledge_item_tags as _sync_knowledge_item_tags


def list_knowledge_items(
    category: Optional[str] = None,
    status: Optional[str] = None,
    tag: Optional[str] = None,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    owner_role: Optional[str] = None,
    db: Session = Depends(get_db),
):
    scoped_owner_role = None
    role_filter = legacy_runtime._owner_role_filter_for_admin(KnowledgeItem, owner_role)
    if role_filter is not None:
        scoped_owner_role = owner_role
    rows = _knowledge_list_knowledge_items(
        db,
        category=category,
        status=status,
        tag=tag,
        keyword=q,
        owner_role=scoped_owner_role,
        page=page,
        size=size,
    )
    rows = _attach_knowledge_item_tags(db, rows)
    return _knowledge_attach_related_notes(db, rows)


def list_knowledge_item_categories(owner_role: Optional[str] = None, db: Session = Depends(get_db)):
    legacy_runtime._owner_role_filter_for_admin(KnowledgeCategory, owner_role)
    scoped_owner_role = owner_role if owner_role in {"admin", "user"} else None
    return {"items": _knowledge_list_categories(db, owner_role=scoped_owner_role)}


def create_knowledge_item_category(payload: Dict[str, Any], db: Session = Depends(get_db)):
    name = _knowledge_normalize_category_name((payload or {}).get("name"))
    created = _knowledge_create_category(db, name=name, owner_role=legacy_runtime._owner_role_value_for_create())
    return {"name": created}


def delete_knowledge_item_category(category_name: str, db: Session = Depends(get_db)):
    name = _knowledge_normalize_category_name(category_name)
    _knowledge_delete_category(db, name=name, owner_role=legacy_runtime._owner_role_value_for_create())
    return {"ok": True}


def create_knowledge_item(data: KnowledgeItemCreate, db: Session = Depends(get_db)):
    payload = _knowledge_normalize_payload(data.model_dump())
    tags_raw = payload.pop("tags", None) if "tags" in payload else None
    related_note_ids_raw = payload.pop("related_note_ids", None) if "related_note_ids" in payload else None
    obj = KnowledgeItem(**payload, owner_role=legacy_runtime._owner_role_value_for_create())
    db.add(obj)
    db.flush()
    obj.tags_text = _serialize_legacy_tags(_normalize_tag_list(tags_raw))
    _sync_knowledge_item_tags(db, obj.id, _normalize_tag_list(tags_raw))
    _knowledge_sync_note_links(db, obj.id, _knowledge_normalize_related_note_ids(related_note_ids_raw))
    db.commit()
    db.refresh(obj)
    rows = _attach_knowledge_item_tags(db, [obj])
    rows = _knowledge_attach_related_notes(db, rows)
    return rows[0]


def get_knowledge_item(item_id: int, db: Session = Depends(get_db)):
    row = db.query(KnowledgeItem).filter(KnowledgeItem.id == item_id, KnowledgeItem.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Knowledge item not found")
    rows = _attach_knowledge_item_tags(db, [row])
    rows = _knowledge_attach_related_notes(db, rows)
    return rows[0]


def update_knowledge_item(item_id: int, data: KnowledgeItemUpdate, db: Session = Depends(get_db)):
    row = db.query(KnowledgeItem).filter(KnowledgeItem.id == item_id, KnowledgeItem.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Knowledge item not found")
    payload = _knowledge_normalize_payload(data.model_dump(exclude_unset=True))
    tags_raw = payload.pop("tags", None) if "tags" in payload else None
    related_note_ids_raw = payload.pop("related_note_ids", None) if "related_note_ids" in payload else None
    for key, value in payload.items():
        setattr(row, key, value)
    if tags_raw is not None:
        tag_names = _normalize_tag_list(tags_raw)
        row.tags_text = _serialize_legacy_tags(tag_names)
        db.flush()
        _sync_knowledge_item_tags(db, row.id, tag_names)
    if related_note_ids_raw is not None:
        db.flush()
        _knowledge_sync_note_links(db, row.id, _knowledge_normalize_related_note_ids(related_note_ids_raw))
    db.commit()
    db.refresh(row)
    rows = _attach_knowledge_item_tags(db, [row])
    rows = _knowledge_attach_related_notes(db, rows)
    return rows[0]


def delete_knowledge_item(item_id: int, db: Session = Depends(get_db)):
    row = db.query(KnowledgeItem).filter(KnowledgeItem.id == item_id, KnowledgeItem.is_deleted == False).first()  # noqa: E712
    if not row:
        raise HTTPException(404, "Knowledge item not found")
    row.is_deleted = True
    row.deleted_at = datetime.now()
    db.commit()
    return {"ok": True}
