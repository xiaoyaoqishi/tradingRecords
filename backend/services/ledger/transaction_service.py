from datetime import date, datetime
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from core.errors import AppError
from models import LedgerAccount, LedgerCategory, LedgerTransaction
from services.ledger import apply_owner_scope, ensure_row_visible, is_admin_role, owner_role_for_create


def transaction_to_item(row: LedgerTransaction) -> dict:
    return {
        "id": row.id,
        "occurred_at": row.occurred_at,
        "posted_date": row.posted_date,
        "account_id": row.account_id,
        "counterparty_account_id": row.counterparty_account_id,
        "category_id": row.category_id,
        "direction": row.direction,
        "transaction_type": row.transaction_type,
        "amount": float(row.amount),
        "currency": row.currency,
        "merchant": row.merchant,
        "description": row.description,
        "note": row.note,
        "external_ref": row.external_ref,
        "source": row.source,
        "linked_transaction_id": row.linked_transaction_id,
        "is_cleared": bool(row.is_cleared),
        "owner_role": row.owner_role,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _ensure_account_visible(db: Session, account_id: int, role: str) -> LedgerAccount:
    account = db.query(LedgerAccount).filter(LedgerAccount.id == account_id, LedgerAccount.is_deleted == False).first()  # noqa: E712
    if not account:
        raise AppError("invalid_account", "账户不存在", status_code=400)
    ensure_row_visible(account.owner_role, role)
    return account


def _ensure_category_visible(db: Session, category_id: int, role: str) -> LedgerCategory:
    category = db.query(LedgerCategory).filter(LedgerCategory.id == category_id, LedgerCategory.is_deleted == False).first()  # noqa: E712
    if not category:
        raise AppError("invalid_category", "分类不存在", status_code=400)
    ensure_row_visible(category.owner_role, role)
    return category


def _ensure_linked_transaction_visible(db: Session, transaction_id: int, role: str) -> LedgerTransaction:
    txn = db.query(LedgerTransaction).filter(LedgerTransaction.id == transaction_id, LedgerTransaction.is_deleted == False).first()  # noqa: E712
    if not txn:
        raise AppError("invalid_linked_transaction", "关联流水不存在", status_code=400)
    ensure_row_visible(txn.owner_role, role)
    return txn


def _validate_business_rules(db: Session, payload: dict, role: str, owner_role: Optional[str] = None, updating_id: Optional[int] = None) -> None:
    account_id = payload.get("account_id")
    if not account_id:
        raise AppError("invalid_payload", "account_id 必填", status_code=400)
    account = _ensure_account_visible(db, int(account_id), role)

    target_owner_role = owner_role or account.owner_role

    counterparty_account_id = payload.get("counterparty_account_id")
    category_id = payload.get("category_id")
    direction = str(payload.get("direction") or "").strip().lower()
    transaction_type = str(payload.get("transaction_type") or "").strip().lower()
    amount = float(payload.get("amount") or 0)

    if amount <= 0:
        raise AppError("invalid_amount", "amount 必须大于 0", status_code=400)

    if transaction_type == "transfer":
        if not counterparty_account_id:
            raise AppError("invalid_transfer", "transfer 必须提供 counterparty_account_id", status_code=400)
        if int(counterparty_account_id) == int(account_id):
            raise AppError("invalid_transfer", "转出和转入账户不能相同", status_code=400)
        if direction != "neutral":
            raise AppError("invalid_transfer", "transfer 的 direction 必须是 neutral", status_code=400)
        counterparty = _ensure_account_visible(db, int(counterparty_account_id), role)
        if counterparty.owner_role != target_owner_role:
            raise AppError("invalid_transfer", "counterparty_account owner_role 不匹配", status_code=400)
    elif counterparty_account_id:
        _ensure_account_visible(db, int(counterparty_account_id), role)

    if transaction_type == "refund" and direction != "income":
        raise AppError("invalid_refund", "refund 的 direction 必须是 income", status_code=400)

    if transaction_type == "expense" and not category_id:
        raise AppError("invalid_expense", "expense 必须提供 category_id", status_code=400)

    if category_id:
        category = _ensure_category_visible(db, int(category_id), role)
        if category.owner_role != target_owner_role:
            raise AppError("invalid_category", "category owner_role 不匹配", status_code=400)

    linked_transaction_id = payload.get("linked_transaction_id")
    if linked_transaction_id:
        linked = _ensure_linked_transaction_visible(db, int(linked_transaction_id), role)
        if updating_id and linked.id == updating_id:
            raise AppError("invalid_linked_transaction", "linked_transaction_id 不能引用自身", status_code=400)

    if account.owner_role != target_owner_role:
        raise AppError("invalid_account", "account owner_role 不匹配", status_code=400)


def _get_transaction_or_404(db: Session, transaction_id: int, role: str) -> LedgerTransaction:
    row = db.query(LedgerTransaction).filter(LedgerTransaction.id == transaction_id, LedgerTransaction.is_deleted == False).first()  # noqa: E712
    if not row:
        raise AppError("not_found", "流水不存在", status_code=404)
    ensure_row_visible(row.owner_role, role)
    return row


def _apply_date_range(query, date_from: Optional[date], date_to: Optional[date]):
    if date_from:
        query = query.filter(func.date(LedgerTransaction.occurred_at) >= date_from)
    if date_to:
        query = query.filter(func.date(LedgerTransaction.occurred_at) <= date_to)
    return query


def list_transactions(db: Session, role: str, query, owner_role: Optional[str] = None) -> dict:
    q = db.query(LedgerTransaction).filter(LedgerTransaction.is_deleted == False)  # noqa: E712
    q = apply_owner_scope(q, LedgerTransaction, role, owner_role=owner_role)

    if query.account_id:
        q = q.filter(LedgerTransaction.account_id == query.account_id)
    if query.category_id:
        q = q.filter(LedgerTransaction.category_id == query.category_id)
    if query.transaction_type:
        q = q.filter(LedgerTransaction.transaction_type == query.transaction_type.value)
    if query.direction:
        q = q.filter(LedgerTransaction.direction == query.direction.value)
    if query.keyword:
        kw = query.keyword.strip()
        if kw:
            q = q.filter(
                or_(
                    LedgerTransaction.merchant.contains(kw),
                    LedgerTransaction.description.contains(kw),
                    LedgerTransaction.note.contains(kw),
                )
            )
    if query.source:
        q = q.filter(LedgerTransaction.source == query.source.strip())
    q = _apply_date_range(q, query.date_from, query.date_to)

    rows = q.order_by(LedgerTransaction.occurred_at.desc(), LedgerTransaction.id.desc()).all()
    return {
        "items": [transaction_to_item(row) for row in rows],
        "total": len(rows),
    }


def get_transaction(db: Session, transaction_id: int, role: str) -> dict:
    row = _get_transaction_or_404(db, transaction_id, role)
    return transaction_to_item(row)


def create_transaction(db: Session, payload, role: str, apply_rules: bool = True) -> dict:
    owner_role = owner_role_for_create(role)
    data = payload.model_dump()

    data["direction"] = data["direction"].value if hasattr(data["direction"], "value") else str(data["direction"])
    data["transaction_type"] = data["transaction_type"].value if hasattr(data["transaction_type"], "value") else str(data["transaction_type"])
    data["owner_role"] = owner_role

    rule_result = {
        "matched_rule_ids": [],
        "matched_rule_names": [],
        "applied_actions": [],
    }
    if apply_rules:
        from services.ledger import rule_service

        applied = rule_service.apply_rules_to_transaction(db, role=role, tx_like_payload=data, owner_role=owner_role)
        data = applied["payload"]
        rule_result = {
            "matched_rule_ids": applied["matched_rule_ids"],
            "matched_rule_names": applied["matched_rule_names"],
            "applied_actions": applied["applied_actions"],
        }

    _validate_business_rules(db, data, role, owner_role=owner_role)

    row = LedgerTransaction(**data)
    db.add(row)
    db.commit()
    db.refresh(row)
    out = transaction_to_item(row)
    out["matched_rules"] = rule_result
    return out


def update_transaction(db: Session, transaction_id: int, payload, role: str, apply_rules: bool = True) -> dict:
    row = _get_transaction_or_404(db, transaction_id, role)
    patch = payload.model_dump(exclude_unset=True)

    merged = {
        "occurred_at": row.occurred_at,
        "posted_date": row.posted_date,
        "account_id": row.account_id,
        "counterparty_account_id": row.counterparty_account_id,
        "category_id": row.category_id,
        "direction": row.direction,
        "transaction_type": row.transaction_type,
        "amount": row.amount,
        "currency": row.currency,
        "merchant": row.merchant,
        "description": row.description,
        "note": row.note,
        "external_ref": row.external_ref,
        "source": row.source,
        "linked_transaction_id": row.linked_transaction_id,
        "is_cleared": row.is_cleared,
    }
    merged.update(patch)

    if hasattr(merged.get("direction"), "value"):
        merged["direction"] = merged["direction"].value
    if hasattr(merged.get("transaction_type"), "value"):
        merged["transaction_type"] = merged["transaction_type"].value

    rule_result = {
        "matched_rule_ids": [],
        "matched_rule_names": [],
        "applied_actions": [],
    }
    if apply_rules:
        from services.ledger import rule_service

        applied = rule_service.apply_rules_to_transaction(db, role=role, tx_like_payload=merged, owner_role=row.owner_role)
        merged = applied["payload"]
        rule_result = {
            "matched_rule_ids": applied["matched_rule_ids"],
            "matched_rule_names": applied["matched_rule_names"],
            "applied_actions": applied["applied_actions"],
        }

    _validate_business_rules(db, merged, role, owner_role=row.owner_role, updating_id=row.id)

    for key, value in merged.items():
        if hasattr(value, "value"):
            value = value.value
        setattr(row, key, value)

    db.commit()
    db.refresh(row)
    out = transaction_to_item(row)
    out["matched_rules"] = rule_result
    return out


def delete_transaction(db: Session, transaction_id: int, role: str) -> dict:
    row = _get_transaction_or_404(db, transaction_id, role)
    row.is_deleted = True
    row.deleted_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


def calculate_account_balance_deltas(
    db: Session,
    role: str,
    owner_role: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict[int, float]:
    q = db.query(LedgerTransaction).filter(LedgerTransaction.is_deleted == False)  # noqa: E712
    q = apply_owner_scope(q, LedgerTransaction, role, owner_role=owner_role)
    q = _apply_date_range(q, date_from, date_to)
    rows = q.all()

    balances: dict[int, float] = {}
    for tx in rows:
        amount = float(tx.amount or 0)
        if tx.transaction_type == "transfer":
            if tx.account_id:
                balances[tx.account_id] = balances.get(tx.account_id, 0.0) - amount
            if tx.counterparty_account_id:
                balances[tx.counterparty_account_id] = balances.get(tx.counterparty_account_id, 0.0) + amount
            continue

        if tx.transaction_type in {"income", "refund", "interest"}:
            balances[tx.account_id] = balances.get(tx.account_id, 0.0) + amount
        elif tx.transaction_type in {"expense", "fee", "repayment"}:
            balances[tx.account_id] = balances.get(tx.account_id, 0.0) - amount
        elif tx.transaction_type == "adjustment":
            if tx.direction == "income":
                balances[tx.account_id] = balances.get(tx.account_id, 0.0) + amount
            elif tx.direction == "expense":
                balances[tx.account_id] = balances.get(tx.account_id, 0.0) - amount
        else:
            if tx.direction == "income":
                balances[tx.account_id] = balances.get(tx.account_id, 0.0) + amount
            elif tx.direction == "expense":
                balances[tx.account_id] = balances.get(tx.account_id, 0.0) - amount
    return balances


def count_transactions(
    db: Session,
    role: str,
    owner_role: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> int:
    q = db.query(LedgerTransaction).filter(LedgerTransaction.is_deleted == False)  # noqa: E712
    q = apply_owner_scope(q, LedgerTransaction, role, owner_role=owner_role)
    q = _apply_date_range(q, date_from, date_to)
    return q.count()


def list_recent_transactions(
    db: Session,
    role: str,
    owner_role: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = 10,
) -> list[dict]:
    q = db.query(LedgerTransaction).filter(LedgerTransaction.is_deleted == False)  # noqa: E712
    q = apply_owner_scope(q, LedgerTransaction, role, owner_role=owner_role)
    q = _apply_date_range(q, date_from, date_to)
    rows = q.order_by(LedgerTransaction.occurred_at.desc(), LedgerTransaction.id.desc()).limit(limit).all()
    return [transaction_to_item(row) for row in rows]


def top_expense_categories(
    db: Session,
    role: str,
    owner_role: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = 5,
) -> list[dict]:
    q = db.query(LedgerTransaction).filter(
        LedgerTransaction.is_deleted == False,  # noqa: E712
        LedgerTransaction.direction == "expense",
        LedgerTransaction.transaction_type.in_(["expense", "fee"]),
        LedgerTransaction.category_id.isnot(None),
    )
    q = apply_owner_scope(q, LedgerTransaction, role, owner_role=owner_role)
    q = _apply_date_range(q, date_from, date_to)

    grouped = (
        q.with_entities(
            LedgerTransaction.category_id,
            func.coalesce(func.sum(LedgerTransaction.amount), 0.0).label("amount_total"),
        )
        .group_by(LedgerTransaction.category_id)
        .order_by(func.sum(LedgerTransaction.amount).desc())
        .limit(limit)
        .all()
    )

    category_ids = [x.category_id for x in grouped if x.category_id]
    category_map = {}
    if category_ids:
        categories_q = db.query(LedgerCategory).filter(LedgerCategory.id.in_(category_ids), LedgerCategory.is_deleted == False)  # noqa: E712
        categories = categories_q.all()
        category_map = {c.id: c for c in categories}

    items = []
    for row in grouped:
        category = category_map.get(row.category_id)
        items.append(
            {
                "category_id": row.category_id,
                "category_name": category.name if category else "(deleted)",
                "amount": float(row.amount_total or 0),
            }
        )
    return items


def summarize_income_expense(
    db: Session,
    role: str,
    owner_role: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    q = db.query(LedgerTransaction).filter(LedgerTransaction.is_deleted == False)  # noqa: E712
    q = apply_owner_scope(q, LedgerTransaction, role, owner_role=owner_role)
    q = _apply_date_range(q, date_from, date_to)

    income_total = 0.0
    expense_total = 0.0
    fee_total = 0.0
    repayment_total = 0.0

    for tx in q.all():
        amount = float(tx.amount or 0)
        tx_type = tx.transaction_type

        if tx_type in {"income", "refund", "interest"}:
            income_total += amount
        if tx_type == "expense" and tx.direction == "expense":
            expense_total += amount
        if tx_type == "fee":
            fee_total += amount
        if tx_type == "repayment":
            repayment_total += amount

    return {
        "income_total": income_total,
        "expense_total": expense_total,
        "fee_total": fee_total,
        "repayment_total": repayment_total,
    }
