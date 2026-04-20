from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from core.errors import AppError
from models import LedgerAccount
from services.ledger import apply_owner_scope, ensure_row_visible, owner_role_for_create
from services.ledger.transaction_service import calculate_account_balance_deltas


def _account_to_item(account: LedgerAccount, current_balance: float) -> dict:
    return {
        "id": account.id,
        "name": account.name,
        "account_type": account.account_type,
        "currency": account.currency,
        "initial_balance": float(account.initial_balance or 0),
        "current_balance": float(current_balance),
        "is_active": bool(account.is_active),
        "notes": account.notes,
        "owner_role": account.owner_role,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }


def _ensure_name_unique(db: Session, name: str, owner_role: str, exclude_id: Optional[int] = None) -> None:
    q = db.query(LedgerAccount).filter(
        LedgerAccount.name == name,
        LedgerAccount.owner_role == owner_role,
        LedgerAccount.is_deleted == False,  # noqa: E712
    )
    if exclude_id:
        q = q.filter(LedgerAccount.id != exclude_id)
    exists = q.first()
    if exists:
        raise AppError("ledger_account_name_exists", "账户名称已存在", status_code=400)


def _get_account_or_404(db: Session, account_id: int, role: str) -> LedgerAccount:
    row = db.query(LedgerAccount).filter(LedgerAccount.id == account_id, LedgerAccount.is_deleted == False).first()  # noqa: E712
    if not row:
        raise AppError("not_found", "账户不存在", status_code=404)
    ensure_row_visible(row.owner_role, role)
    return row


def list_accounts(db: Session, role: str, owner_role: Optional[str] = None) -> dict:
    q = db.query(LedgerAccount).filter(LedgerAccount.is_deleted == False)  # noqa: E712
    q = apply_owner_scope(q, LedgerAccount, role, owner_role=owner_role)
    rows = q.order_by(LedgerAccount.id.desc()).all()

    deltas = calculate_account_balance_deltas(db, role=role, owner_role=owner_role)
    items = []
    for row in rows:
        current_balance = float(row.initial_balance or 0) + float(deltas.get(row.id, 0.0))
        items.append(_account_to_item(row, current_balance))
    return {"items": items}


def create_account(db: Session, payload, role: str) -> dict:
    owner_role = owner_role_for_create(role)
    _ensure_name_unique(db, payload.name.strip(), owner_role)

    row = LedgerAccount(
        name=payload.name.strip(),
        account_type=payload.account_type.value if hasattr(payload.account_type, "value") else str(payload.account_type),
        currency=payload.currency.strip().upper(),
        initial_balance=payload.initial_balance,
        is_active=payload.is_active,
        notes=payload.notes,
        owner_role=owner_role,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _account_to_item(row, float(row.initial_balance or 0))


def update_account(db: Session, account_id: int, payload, role: str) -> dict:
    row = _get_account_or_404(db, account_id, role)
    data = payload.model_dump(exclude_unset=True)

    if "name" in data and data["name"] is not None:
        normalized_name = data["name"].strip()
        _ensure_name_unique(db, normalized_name, row.owner_role, exclude_id=row.id)
        row.name = normalized_name
    if "account_type" in data and data["account_type"] is not None:
        row.account_type = data["account_type"].value if hasattr(data["account_type"], "value") else str(data["account_type"])
    if "currency" in data and data["currency"] is not None:
        row.currency = data["currency"].strip().upper()
    if "initial_balance" in data:
        row.initial_balance = data["initial_balance"]
    if "is_active" in data:
        row.is_active = data["is_active"]
    if "notes" in data:
        row.notes = data["notes"]

    db.commit()
    db.refresh(row)
    deltas = calculate_account_balance_deltas(db, role=role, owner_role=row.owner_role)
    current_balance = float(row.initial_balance or 0) + float(deltas.get(row.id, 0.0))
    return _account_to_item(row, current_balance)


def delete_account(db: Session, account_id: int, role: str) -> dict:
    row = _get_account_or_404(db, account_id, role)
    row.is_deleted = True
    row.deleted_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
