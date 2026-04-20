import json
from collections import Counter
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from core.errors import AppError
from models import LedgerCategory, LedgerRule, LedgerTransaction
from services.ledger import apply_owner_scope, ensure_row_visible, owner_role_for_create

STRING_CONTAINS_KEYS = {
    "merchant_contains": "merchant",
    "description_contains": "description",
    "note_contains": "note",
    "external_ref_contains": "external_ref",
}


def _norm_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _norm_lower(value: Any) -> str:
    return _norm_str(value).lower()


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _json_load(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except Exception:
        parsed = {}
    return parsed if isinstance(parsed, dict) else {}


def _json_dump(data: dict[str, Any]) -> str:
    return json.dumps(data or {}, ensure_ascii=False)


def _rule_item(row: LedgerRule) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "is_active": bool(row.is_active),
        "priority": int(row.priority or 100),
        "match_json": _json_load(row.match_json),
        "action_json": _json_load(row.action_json),
        "owner_role": row.owner_role,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _validate_rule_payload(match_json: dict[str, Any], action_json: dict[str, Any], db: Session, role: str) -> None:
    if not isinstance(match_json, dict) or not any(v not in (None, "", [], {}) for v in match_json.values()):
        raise AppError("invalid_rule_match", "至少需要一个匹配条件", status_code=400)
    if not isinstance(action_json, dict) or not any(v not in (None, "", [], {}) for v in action_json.values()):
        raise AppError("invalid_rule_action", "至少需要一个动作", status_code=400)

    category_id = action_json.get("set_category_id")
    if category_id is not None:
        try:
            cid = int(category_id)
        except Exception:
            raise AppError("invalid_rule_action", "set_category_id 必须为正整数", status_code=400)
        category = db.query(LedgerCategory).filter(LedgerCategory.id == cid, LedgerCategory.is_deleted == False).first()  # noqa: E712
        if not category:
            raise AppError("invalid_rule_action", "set_category_id 对应分类不存在", status_code=400)
        ensure_row_visible(category.owner_role, role)

    tx_type = _norm_lower(action_json.get("set_transaction_type"))
    if tx_type and tx_type not in {"income", "expense", "transfer", "refund", "repayment", "fee", "interest", "adjustment"}:
        raise AppError("invalid_rule_action", "set_transaction_type 非法", status_code=400)

    direction = _norm_lower(action_json.get("set_direction"))
    if direction and direction not in {"income", "expense", "neutral"}:
        raise AppError("invalid_rule_action", "set_direction 非法", status_code=400)


def _string_contains(matcher_value: Any, target_text: str) -> bool:
    values: list[str] = []
    if isinstance(matcher_value, list):
        values = [_norm_lower(x) for x in matcher_value if _norm_str(x)]
    else:
        one = _norm_lower(matcher_value)
        if one:
            values = [one]

    if not values:
        return False

    src = _norm_lower(target_text)
    return any(v in src for v in values)


def evaluate_rule(rule: dict[str, Any], tx_like_payload: dict[str, Any]) -> bool:
    match_json = rule.get("match_json") or {}

    for cond_key, field_name in STRING_CONTAINS_KEYS.items():
        cond_val = match_json.get(cond_key)
        if cond_val in (None, "", []):
            continue
        if not _string_contains(cond_val, tx_like_payload.get(field_name)):
            return False

    if match_json.get("account_id") not in (None, ""):
        if int(match_json["account_id"]) != int(tx_like_payload.get("account_id") or 0):
            return False

    if match_json.get("transaction_type") not in (None, ""):
        if _norm_lower(match_json.get("transaction_type")) != _norm_lower(tx_like_payload.get("transaction_type")):
            return False

    if match_json.get("direction") not in (None, ""):
        if _norm_lower(match_json.get("direction")) != _norm_lower(tx_like_payload.get("direction")):
            return False

    amount = _to_float(tx_like_payload.get("amount"))
    if match_json.get("amount_eq") not in (None, ""):
        target = _to_float(match_json.get("amount_eq"))
        if target is None or amount is None or amount != target:
            return False

    if match_json.get("amount_gte") not in (None, ""):
        target = _to_float(match_json.get("amount_gte"))
        if target is None or amount is None or amount < target:
            return False

    if match_json.get("amount_lte") not in (None, ""):
        target = _to_float(match_json.get("amount_lte"))
        if target is None or amount is None or amount > target:
            return False

    if match_json.get("source") not in (None, ""):
        if _norm_lower(match_json.get("source")) != _norm_lower(tx_like_payload.get("source")):
            return False

    if match_json.get("currency") not in (None, ""):
        if _norm_lower(match_json.get("currency")) != _norm_lower(tx_like_payload.get("currency")):
            return False

    return True


def apply_rule_actions(rule: dict[str, Any], tx_like_payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    action_json = rule.get("action_json") or {}
    out = dict(tx_like_payload)
    changed_fields: list[str] = []

    def _set_if_changed(key: str, value: Any):
        nonlocal out, changed_fields
        if out.get(key) != value:
            out[key] = value
            changed_fields.append(key)

    if action_json.get("set_category_id") not in (None, ""):
        _set_if_changed("category_id", int(action_json.get("set_category_id")))

    if _norm_str(action_json.get("set_transaction_type")):
        _set_if_changed("transaction_type", _norm_lower(action_json.get("set_transaction_type")))

    if _norm_str(action_json.get("set_direction")):
        _set_if_changed("direction", _norm_lower(action_json.get("set_direction")))

    if _norm_str(action_json.get("set_merchant")):
        _set_if_changed("merchant", _norm_str(action_json.get("set_merchant")))

    if action_json.get("set_is_cleared") is not None:
        _set_if_changed("is_cleared", bool(action_json.get("set_is_cleared")))

    append_note = _norm_str(action_json.get("append_note"))
    if append_note:
        old_note = _norm_str(out.get("note"))
        merged = append_note if not old_note else f"{old_note}\n{append_note}"
        _set_if_changed("note", merged)

    add_tag_text = _norm_str(action_json.get("add_tag_text"))
    if add_tag_text:
        old_note = _norm_str(out.get("note"))
        tag_note = f"#{add_tag_text}" if not add_tag_text.startswith("#") else add_tag_text
        merged = tag_note if not old_note else f"{old_note}\n{tag_note}"
        _set_if_changed("note", merged)

    return out, changed_fields


def _active_rules(db: Session, role: str, owner_role: str) -> list[dict[str, Any]]:
    q = db.query(LedgerRule).filter(LedgerRule.is_deleted == False, LedgerRule.is_active == True)  # noqa: E712
    q = apply_owner_scope(q, LedgerRule, role, owner_role=owner_role)
    rows = q.order_by(LedgerRule.priority.asc(), LedgerRule.id.asc()).all()
    return [_rule_item(x) for x in rows]


def apply_active_rules_in_priority_order(db: Session, role: str, owner_role: str, payload: dict[str, Any]) -> dict[str, Any]:
    current = dict(payload)
    matched_rule_ids: list[int] = []
    matched_rule_names: list[str] = []
    applied_actions: list[str] = []
    changed_fields: set[str] = set()

    for rule in _active_rules(db, role, owner_role):
        if not evaluate_rule(rule, current):
            continue
        patched, changed = apply_rule_actions(rule, current)
        current = patched
        matched_rule_ids.append(int(rule["id"]))
        matched_rule_names.append(str(rule["name"]))
        if changed:
            applied_actions.append(f"{rule['name']}: {', '.join(changed)}")
            changed_fields.update(changed)

    return {
        "payload": current,
        "matched_rule_ids": matched_rule_ids,
        "matched_rule_names": matched_rule_names,
        "applied_actions": applied_actions,
        "patched_fields": sorted(changed_fields),
    }


def apply_rules_to_transaction(db: Session, role: str, tx_like_payload: dict[str, Any], owner_role: Optional[str] = None) -> dict[str, Any]:
    target_owner_role = owner_role or owner_role_for_create(role)
    return apply_active_rules_in_priority_order(db, role, target_owner_role, tx_like_payload)


def _tx_to_payload(tx: LedgerTransaction) -> dict[str, Any]:
    return {
        "occurred_at": tx.occurred_at,
        "posted_date": tx.posted_date,
        "account_id": tx.account_id,
        "counterparty_account_id": tx.counterparty_account_id,
        "category_id": tx.category_id,
        "direction": tx.direction,
        "transaction_type": tx.transaction_type,
        "amount": float(tx.amount or 0),
        "currency": tx.currency,
        "merchant": tx.merchant,
        "description": tx.description,
        "note": tx.note,
        "external_ref": tx.external_ref,
        "source": tx.source,
        "is_cleared": bool(tx.is_cleared),
    }


def list_rules(db: Session, role: str) -> dict:
    owner_role = owner_role_for_create(role)
    q = db.query(LedgerRule).filter(LedgerRule.is_deleted == False)  # noqa: E712
    q = apply_owner_scope(q, LedgerRule, role, owner_role=owner_role)
    rows = q.order_by(LedgerRule.priority.asc(), LedgerRule.id.asc()).all()
    return {"items": [_rule_item(x) for x in rows]}


def create_rule(db: Session, role: str, payload) -> dict:
    owner_role = owner_role_for_create(role)
    _validate_rule_payload(payload.match_json, payload.action_json, db, role)

    row = LedgerRule(
        name=payload.name.strip(),
        is_active=bool(payload.is_active),
        priority=int(payload.priority),
        match_json=_json_dump(payload.match_json),
        action_json=_json_dump(payload.action_json),
        owner_role=owner_role,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _rule_item(row)


def update_rule(db: Session, role: str, rule_id: int, payload) -> dict:
    row = db.query(LedgerRule).filter(LedgerRule.id == rule_id, LedgerRule.is_deleted == False).first()  # noqa: E712
    if not row:
        raise AppError("not_found", "规则不存在", status_code=404)
    ensure_row_visible(row.owner_role, role)

    data = payload.model_dump(exclude_unset=True)
    next_match = _json_load(row.match_json)
    next_action = _json_load(row.action_json)

    if "name" in data and data["name"] is not None:
        row.name = data["name"].strip()
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = bool(data["is_active"])
    if "priority" in data and data["priority"] is not None:
        row.priority = int(data["priority"])
    if "match_json" in data and data["match_json"] is not None:
        next_match = data["match_json"]
        row.match_json = _json_dump(next_match)
    if "action_json" in data and data["action_json"] is not None:
        next_action = data["action_json"]
        row.action_json = _json_dump(next_action)

    _validate_rule_payload(next_match, next_action, db, role)
    db.commit()
    db.refresh(row)
    return _rule_item(row)


def delete_rule(db: Session, role: str, rule_id: int) -> dict:
    row = db.query(LedgerRule).filter(LedgerRule.id == rule_id, LedgerRule.is_deleted == False).first()  # noqa: E712
    if not row:
        raise AppError("not_found", "规则不存在", status_code=404)
    ensure_row_visible(row.owner_role, role)
    row.is_deleted = True
    row.deleted_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


def _query_transactions_for_preview(db: Session, role: str, owner_role: str, payload) -> list[LedgerTransaction]:
    q = db.query(LedgerTransaction).filter(LedgerTransaction.is_deleted == False)  # noqa: E712
    q = apply_owner_scope(q, LedgerTransaction, role, owner_role=owner_role)

    if payload.transaction_ids:
        q = q.filter(LedgerTransaction.id.in_(payload.transaction_ids))
    if payload.account_id:
        q = q.filter(LedgerTransaction.account_id == payload.account_id)
    if payload.category_id:
        q = q.filter(LedgerTransaction.category_id == payload.category_id)
    if payload.source:
        q = q.filter(LedgerTransaction.source == payload.source)
    if payload.date_from:
        q = q.filter(LedgerTransaction.occurred_at >= datetime.combine(payload.date_from, datetime.min.time()))
    if payload.date_to:
        q = q.filter(LedgerTransaction.occurred_at <= datetime.combine(payload.date_to, datetime.max.time()))

    return q.order_by(LedgerTransaction.occurred_at.desc(), LedgerTransaction.id.desc()).limit(payload.limit).all()


def preview_rules_on_transactions(db: Session, role: str, payload) -> dict:
    owner_role = owner_role_for_create(role)
    items: list[dict[str, Any]] = []

    if payload.transaction:
        applied = apply_active_rules_in_priority_order(db, role, owner_role, payload.transaction)
        items.append(
            {
                "transaction_id": None,
                "before": payload.transaction,
                "after": applied["payload"],
                "matched_rule_ids": applied["matched_rule_ids"],
                "matched_rule_names": applied["matched_rule_names"],
                "applied_actions": applied["applied_actions"],
                "patched_fields": applied["patched_fields"],
            }
        )

    db_rows = _query_transactions_for_preview(db, role, owner_role, payload)
    for row in db_rows:
        before = _tx_to_payload(row)
        applied = apply_active_rules_in_priority_order(db, role, owner_role, before)
        items.append(
            {
                "transaction_id": row.id,
                "before": before,
                "after": applied["payload"],
                "matched_rule_ids": applied["matched_rule_ids"],
                "matched_rule_names": applied["matched_rule_names"],
                "applied_actions": applied["applied_actions"],
                "patched_fields": applied["patched_fields"],
            }
        )

    return {"items": items}


def bulk_apply_rules(db: Session, role: str, payload) -> dict:
    owner_role = owner_role_for_create(role)
    q = db.query(LedgerTransaction).filter(LedgerTransaction.is_deleted == False)  # noqa: E712
    q = apply_owner_scope(q, LedgerTransaction, role, owner_role=owner_role)

    if payload.transaction_ids:
        q = q.filter(LedgerTransaction.id.in_(payload.transaction_ids))
    if payload.account_id:
        q = q.filter(LedgerTransaction.account_id == payload.account_id)
    if payload.category_id:
        q = q.filter(LedgerTransaction.category_id == payload.category_id)
    if payload.source:
        q = q.filter(LedgerTransaction.source == payload.source)
    if payload.date_from:
        q = q.filter(LedgerTransaction.occurred_at >= datetime.combine(payload.date_from, datetime.min.time()))
    if payload.date_to:
        q = q.filter(LedgerTransaction.occurred_at <= datetime.combine(payload.date_to, datetime.max.time()))

    rows = q.order_by(LedgerTransaction.id.asc()).all()

    scanned_count = len(rows)
    updated_count = 0
    skipped_count = 0
    error_count = 0
    rule_counter: Counter[str] = Counter()

    from services.ledger import transaction_service

    for row in rows:
        before = _tx_to_payload(row)
        applied = apply_active_rules_in_priority_order(db, role, owner_role, before)
        after = applied["payload"]

        if not applied["patched_fields"]:
            skipped_count += 1
            continue

        try:
            transaction_service._validate_business_rules(db, after, role, owner_role=row.owner_role, updating_id=row.id)
        except AppError:
            error_count += 1
            continue

        changed = False
        for key, value in after.items():
            old = getattr(row, key)
            if old != value:
                setattr(row, key, value)
                changed = True

        if changed:
            updated_count += 1
            for name in applied["matched_rule_names"]:
                rule_counter[name] += 1
        else:
            skipped_count += 1

    db.commit()
    return {
        "scanned_count": scanned_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "error_count": error_count,
        "per_rule_hit_summary": dict(rule_counter),
    }
