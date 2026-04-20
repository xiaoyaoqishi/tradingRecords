from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from core.errors import AppError
from models import LedgerCategory, LedgerTransaction
from services.ledger import apply_owner_scope, ensure_row_visible, owner_role_for_create


def _category_to_item(row: LedgerCategory) -> dict:
    return {
        "id": row.id,
        "parent_id": row.parent_id,
        "name": row.name,
        "category_type": row.category_type,
        "sort_order": row.sort_order,
        "is_active": bool(row.is_active),
        "owner_role": row.owner_role,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _get_category_or_404(db: Session, category_id: int, role: str) -> LedgerCategory:
    row = db.query(LedgerCategory).filter(LedgerCategory.id == category_id, LedgerCategory.is_deleted == False).first()  # noqa: E712
    if not row:
        raise AppError("not_found", "分类不存在", status_code=404)
    ensure_row_visible(row.owner_role, role)
    return row


def _ensure_name_unique(db: Session, name: str, owner_role: str, exclude_id: Optional[int] = None) -> None:
    q = db.query(LedgerCategory).filter(
        LedgerCategory.name == name,
        LedgerCategory.owner_role == owner_role,
        LedgerCategory.is_deleted == False,  # noqa: E712
    )
    if exclude_id:
        q = q.filter(LedgerCategory.id != exclude_id)
    if q.first():
        raise AppError("ledger_category_name_exists", "分类名称已存在", status_code=400)


def _validate_parent(db: Session, parent_id: Optional[int], role: str, owner_role: str, self_id: Optional[int] = None) -> None:
    if not parent_id:
        return
    if self_id and parent_id == self_id:
        raise AppError("invalid_parent", "parent_id 不能是自身", status_code=400)
    parent = db.query(LedgerCategory).filter(LedgerCategory.id == parent_id, LedgerCategory.is_deleted == False).first()  # noqa: E712
    if not parent:
        raise AppError("invalid_parent", "父分类不存在", status_code=400)
    ensure_row_visible(parent.owner_role, role)
    if parent.owner_role != owner_role:
        raise AppError("invalid_parent", "父分类 owner_role 不匹配", status_code=400)
    if parent.parent_id is not None:
        raise AppError("invalid_parent", "仅支持两层分类", status_code=400)


def list_categories(db: Session, role: str, category_type: Optional[str] = None, owner_role: Optional[str] = None) -> dict:
    q = db.query(LedgerCategory).filter(LedgerCategory.is_deleted == False)  # noqa: E712
    q = apply_owner_scope(q, LedgerCategory, role, owner_role=owner_role)
    if category_type:
        q = q.filter(LedgerCategory.category_type == category_type)
    rows = q.order_by(LedgerCategory.sort_order.asc(), LedgerCategory.id.asc()).all()
    return {"items": [_category_to_item(row) for row in rows]}


def create_category(db: Session, payload, role: str) -> dict:
    owner_role = owner_role_for_create(role)
    _ensure_name_unique(db, payload.name.strip(), owner_role)
    _validate_parent(db, payload.parent_id, role, owner_role)

    row = LedgerCategory(
        parent_id=payload.parent_id,
        name=payload.name.strip(),
        category_type=payload.category_type.value if hasattr(payload.category_type, "value") else str(payload.category_type),
        sort_order=payload.sort_order,
        is_active=payload.is_active,
        owner_role=owner_role,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _category_to_item(row)


def update_category(db: Session, category_id: int, payload, role: str) -> dict:
    row = _get_category_or_404(db, category_id, role)
    data = payload.model_dump(exclude_unset=True)

    if "name" in data and data["name"] is not None:
        normalized_name = data["name"].strip()
        _ensure_name_unique(db, normalized_name, row.owner_role, exclude_id=row.id)
        row.name = normalized_name

    parent_id = data.get("parent_id", row.parent_id)
    _validate_parent(db, parent_id, role, row.owner_role, self_id=row.id)

    if "parent_id" in data:
        row.parent_id = data["parent_id"]
    if "category_type" in data and data["category_type"] is not None:
        row.category_type = data["category_type"].value if hasattr(data["category_type"], "value") else str(data["category_type"])
    if "sort_order" in data:
        row.sort_order = data["sort_order"]
    if "is_active" in data:
        row.is_active = data["is_active"]

    db.commit()
    db.refresh(row)
    return _category_to_item(row)


def delete_category(db: Session, category_id: int, role: str) -> dict:
    row = _get_category_or_404(db, category_id, role)

    in_use = db.query(LedgerTransaction.id).filter(
        LedgerTransaction.category_id == row.id,
        LedgerTransaction.is_deleted == False,  # noqa: E712
    ).first()
    if in_use:
        raise AppError("ledger_category_in_use", "分类已被流水引用，无法删除", status_code=400)

    row.is_deleted = True
    row.deleted_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
