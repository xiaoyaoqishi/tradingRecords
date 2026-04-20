import csv
import io
import json
from datetime import date, datetime, time
from typing import Any, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from core.errors import AppError
from models import LedgerAccount, LedgerCategory, LedgerImportTemplate, LedgerTransaction
from services.ledger import apply_owner_scope, ensure_row_visible, owner_role_for_create
from services.ledger import transaction_service
from services.ledger import rule_service

VALID_TRANSACTION_TYPES = {
    "income",
    "expense",
    "transfer",
    "refund",
    "repayment",
    "fee",
    "interest",
    "adjustment",
}
VALID_DIRECTIONS = {"income", "expense", "neutral"}


def _normalize_delimiter(delimiter: str) -> str:
    raw = str(delimiter or ",").strip()
    if raw in {"\\t", "tab", "TAB", "制表符"}:
        return "\t"
    if not raw:
        return ","
    return raw[0]


def _normalize_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_upper_str(value: Any, fallback: str = "CNY") -> str:
    text = _normalize_str(value)
    return (text or fallback).upper()


def _normalize_int(value: Any) -> Optional[int]:
    text = _normalize_str(value)
    if text is None:
        return None
    try:
        out = int(float(text))
    except Exception:
        return None
    return out if out > 0 else None


def _parse_float_positive(value: Any) -> Optional[float]:
    text = _normalize_str(value)
    if text is None:
        return None
    try:
        num = float(text.replace(",", ""))
    except Exception:
        return None
    if num == 0:
        return None
    return abs(num)


def _parse_date(value: Any) -> Optional[date]:
    text = _normalize_str(value)
    if text is None:
        return None

    for parser in (
        lambda s: date.fromisoformat(s),
        lambda s: datetime.strptime(s, "%Y/%m/%d").date(),
        lambda s: datetime.strptime(s, "%Y.%m.%d").date(),
        lambda s: datetime.strptime(s, "%Y%m%d").date(),
    ):
        try:
            return parser(text)
        except Exception:
            continue
    return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    text = _normalize_str(value)
    if text is None:
        return None

    normalized = text.replace("Z", "+00:00")
    for parser in (
        lambda s: datetime.fromisoformat(s),
        lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M:%S"),
        lambda s: datetime.strptime(s, "%Y/%m/%d %H:%M:%S"),
        lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M"),
        lambda s: datetime.strptime(s, "%Y/%m/%d %H:%M"),
    ):
        try:
            return parser(normalized)
        except Exception:
            continue

    parsed_date = _parse_date(text)
    if parsed_date is not None:
        return datetime.combine(parsed_date, time(0, 0, 0))
    return None


def _decode_csv_bytes(raw_bytes: bytes, encoding: str) -> str:
    enc = str(encoding or "utf-8").strip() or "utf-8"
    aliases = [enc]
    if enc.lower() == "gbk":
        aliases.append("gb18030")

    for alias in aliases:
        try:
            return raw_bytes.decode(alias)
        except UnicodeDecodeError:
            continue
    raise AppError("invalid_csv_encoding", f"CSV 编码解析失败: {enc}", status_code=400)


def _build_csv_rows(content: str, delimiter: str, has_header: bool) -> tuple[list[str], list[tuple[int, dict[str, str]]]]:
    rows: list[tuple[int, dict[str, str]]] = []
    sio = io.StringIO(content)

    if has_header:
        reader = csv.DictReader(sio, delimiter=delimiter)
        columns = [str(x).strip() for x in (reader.fieldnames or []) if str(x).strip()]
        row_no = 1
        for raw in reader:
            row_no += 1
            row = {str(k): (v if v is not None else "") for k, v in (raw or {}).items() if k is not None}
            rows.append((row_no, row))
        return columns, rows

    reader2 = csv.reader(sio, delimiter=delimiter)
    raw_rows = list(reader2)
    if not raw_rows:
        return [], []

    max_cols = max(len(x) for x in raw_rows)
    columns = [f"col_{idx + 1}" for idx in range(max_cols)]
    for idx, raw in enumerate(raw_rows, start=1):
        row_dict = {columns[col_idx]: (raw[col_idx] if col_idx < len(raw) else "") for col_idx in range(max_cols)}
        rows.append((idx, row_dict))
    return columns, rows


def _resolve_scope_maps(db: Session, role: str, owner_role: str) -> dict[str, Any]:
    accounts_q = db.query(LedgerAccount).filter(LedgerAccount.is_deleted == False)  # noqa: E712
    accounts_q = apply_owner_scope(accounts_q, LedgerAccount, role, owner_role=owner_role)
    accounts = accounts_q.all()

    categories_q = db.query(LedgerCategory).filter(LedgerCategory.is_deleted == False)  # noqa: E712
    categories_q = apply_owner_scope(categories_q, LedgerCategory, role, owner_role=owner_role)
    categories = categories_q.all()

    account_by_name = {str(x.name).strip().lower(): x for x in accounts if str(x.name).strip()}
    account_by_id = {int(x.id): x for x in accounts}

    category_by_name = {str(x.name).strip().lower(): x for x in categories if str(x.name).strip()}
    category_by_id = {int(x.id): x for x in categories}

    return {
        "account_by_name": account_by_name,
        "account_by_id": account_by_id,
        "category_by_name": category_by_name,
        "category_by_id": category_by_id,
    }


def _mapping_value(row: dict[str, Any], mapping: dict[str, str], target_field: str) -> Optional[str]:
    col = _normalize_str(mapping.get(target_field))
    if not col:
        return None
    return _normalize_str(row.get(col))


def _infer_direction(tx_type: Optional[str]) -> Optional[str]:
    if tx_type == "transfer":
        return "neutral"
    if tx_type == "refund":
        return "income"
    if tx_type in {"income", "interest"}:
        return "income"
    if tx_type in {"expense", "fee", "repayment"}:
        return "expense"
    return None


def _resolve_account_id(
    *,
    row: dict[str, Any],
    mapping: dict[str, str],
    maps: dict[str, Any],
    default_account_id: Optional[int],
    errors: list[str],
    warnings: list[str],
    required: bool,
    id_field: str,
    name_field: str,
    title: str,
) -> Optional[int]:
    account_id = _normalize_int(_mapping_value(row, mapping, id_field))
    if account_id:
        if account_id in maps["account_by_id"]:
            return account_id
        errors.append(f"{title} ID 不存在或无权限")
        return None

    account_name = _mapping_value(row, mapping, name_field)
    if account_name:
        found = maps["account_by_name"].get(account_name.strip().lower())
        if found:
            return int(found.id)
        if required:
            errors.append(f"{title}名称未匹配: {account_name}")
        else:
            warnings.append(f"{title}名称未匹配: {account_name}")
        return None

    if default_account_id:
        if default_account_id in maps["account_by_id"]:
            return default_account_id
        errors.append("默认账户无效")
        return None

    if required:
        errors.append(f"{title}不能为空")
    return None


def _resolve_category_id(
    *,
    row: dict[str, Any],
    mapping: dict[str, str],
    maps: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> Optional[int]:
    category_id = _normalize_int(_mapping_value(row, mapping, "category_id"))
    if category_id:
        if category_id in maps["category_by_id"]:
            return category_id
        errors.append("分类 ID 不存在或无权限")
        return None

    category_name = _mapping_value(row, mapping, "category_name")
    if category_name:
        found = maps["category_by_name"].get(category_name.strip().lower())
        if found:
            return int(found.id)
        warnings.append(f"分类名称未匹配: {category_name}")
    return None


def _to_duplicate_key(owner_role: str, record: dict[str, Any]) -> tuple:
    return (
        owner_role,
        record["occurred_at"].replace(microsecond=0).isoformat(),
        round(float(record["amount"]), 2),
        record["transaction_type"],
        int(record["account_id"]),
        (_normalize_str(record.get("merchant")) or "").lower(),
        (_normalize_str(record.get("external_ref")) or "").lower(),
    )


def _is_duplicate(db: Session, owner_role: str, record: dict[str, Any]) -> bool:
    merchant = _normalize_str(record.get("merchant"))
    external_ref = _normalize_str(record.get("external_ref"))

    conditions = [
        LedgerTransaction.owner_role == owner_role,
        LedgerTransaction.is_deleted == False,  # noqa: E712
        LedgerTransaction.occurred_at == record["occurred_at"],
        LedgerTransaction.amount == float(record["amount"]),
        LedgerTransaction.transaction_type == record["transaction_type"],
        LedgerTransaction.account_id == int(record["account_id"]),
    ]

    if merchant:
        conditions.append(LedgerTransaction.merchant == merchant)
    else:
        conditions.append(LedgerTransaction.merchant.is_(None))

    if external_ref:
        conditions.append(LedgerTransaction.external_ref == external_ref)
    else:
        conditions.append(LedgerTransaction.external_ref.is_(None))

    existed = db.query(LedgerTransaction.id).filter(and_(*conditions)).first()
    return bool(existed)


def _normalize_preview_row(
    *,
    db: Session,
    role: str,
    owner_role: str,
    row_no: int,
    row: dict[str, Any],
    payload,
    maps: dict[str, Any],
) -> dict[str, Any]:
    mapping = payload.mapping or {}
    errors: list[str] = []
    warnings: list[str] = []

    occurred_at = _parse_datetime(_mapping_value(row, mapping, "occurred_at"))
    if occurred_at is None:
        errors.append("发生时间无法解析")

    posted_date = _parse_date(_mapping_value(row, mapping, "posted_date"))

    tx_type_raw = _mapping_value(row, mapping, "transaction_type")
    tx_type = (tx_type_raw or (payload.default_transaction_type.value if payload.default_transaction_type else None) or "").lower().strip()
    if not tx_type:
        errors.append("transaction_type 不能为空")
    elif tx_type not in VALID_TRANSACTION_TYPES:
        errors.append(f"transaction_type 不支持: {tx_type}")

    direction_raw = _mapping_value(row, mapping, "direction")
    direction = (
        direction_raw
        or (payload.default_direction.value if payload.default_direction else None)
        or _infer_direction(tx_type)
        or ""
    ).lower().strip()
    if not direction:
        errors.append("direction 不能为空")
    elif direction not in VALID_DIRECTIONS:
        errors.append(f"direction 不支持: {direction}")

    amount = _parse_float_positive(_mapping_value(row, mapping, "amount"))
    if amount is None:
        errors.append("amount 非法或为空")

    account_id = _resolve_account_id(
        row=row,
        mapping=mapping,
        maps=maps,
        default_account_id=payload.default_account_id,
        errors=errors,
        warnings=warnings,
        required=True,
        id_field="account_id",
        name_field="account_name",
        title="账户",
    )

    counterparty_account_id = _resolve_account_id(
        row=row,
        mapping=mapping,
        maps=maps,
        default_account_id=None,
        errors=errors,
        warnings=warnings,
        required=False,
        id_field="counterparty_account_id",
        name_field="counterparty_account_name",
        title="对方账户",
    )

    category_id = _resolve_category_id(row=row, mapping=mapping, maps=maps, errors=errors, warnings=warnings)

    currency = _normalize_upper_str(_mapping_value(row, mapping, "currency") or payload.default_currency, "CNY")
    merchant = _normalize_str(_mapping_value(row, mapping, "merchant"))
    description = _normalize_str(_mapping_value(row, mapping, "description"))
    note = _normalize_str(_mapping_value(row, mapping, "note"))
    external_ref = _normalize_str(_mapping_value(row, mapping, "external_ref"))

    record = {
        "occurred_at": occurred_at,
        "posted_date": posted_date,
        "account_id": account_id,
        "counterparty_account_id": counterparty_account_id,
        "category_id": category_id,
        "direction": direction,
        "transaction_type": tx_type,
        "amount": amount,
        "currency": currency,
        "merchant": merchant,
        "description": description,
        "note": note,
        "external_ref": external_ref,
        "source": "import_csv",
        "is_cleared": False,
    }

    matched_rule_ids: list[int] = []
    matched_rule_names: list[str] = []
    applied_actions: list[str] = []
    patched_fields: list[str] = []

    if not errors and payload.apply_rules:
        applied = rule_service.apply_rules_to_transaction(db, role=role, tx_like_payload=record, owner_role=owner_role)
        record = applied["payload"]
        matched_rule_ids = applied["matched_rule_ids"]
        matched_rule_names = applied["matched_rule_names"]
        applied_actions = applied["applied_actions"]
        patched_fields = applied["patched_fields"]

    if not errors:
        try:
            transaction_service._validate_business_rules(db, record, role, owner_role=owner_role)
        except AppError as exc:
            errors.append(exc.message)

    status = "invalid" if errors else "valid"
    return {
        "row_no": row_no,
        "raw": row,
        "record": record,
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "matched_rules": {
            "ids": matched_rule_ids,
            "names": matched_rule_names,
            "applied_actions": applied_actions,
        },
        "patched_fields": patched_fields,
    }


def preview_import(db: Session, role: str, payload, csv_bytes: bytes) -> dict:
    owner_role = owner_role_for_create(role)
    maps = _resolve_scope_maps(db, role, owner_role)

    text = _decode_csv_bytes(csv_bytes, payload.encoding)
    delimiter = _normalize_delimiter(payload.delimiter)
    columns, rows = _build_csv_rows(text, delimiter=delimiter, has_header=bool(payload.has_header))

    preview_rows: list[dict[str, Any]] = []
    seen_keys: set[tuple] = set()
    stats = {
        "total_rows": 0,
        "valid_rows": 0,
        "duplicate_rows": 0,
        "invalid_rows": 0,
    }

    for row_no, row in rows:
        stats["total_rows"] += 1
        normalized = _normalize_preview_row(
            db=db,
            role=role,
            owner_role=owner_role,
            row_no=row_no,
            row=row,
            payload=payload,
            maps=maps,
        )

        if normalized["status"] == "valid":
            dup_key = _to_duplicate_key(owner_role, normalized["record"])
            if dup_key in seen_keys or _is_duplicate(db, owner_role, normalized["record"]):
                normalized["status"] = "duplicate"
            else:
                seen_keys.add(dup_key)

        if normalized["status"] == "valid":
            stats["valid_rows"] += 1
        elif normalized["status"] == "duplicate":
            stats["duplicate_rows"] += 1
        else:
            stats["invalid_rows"] += 1

        if len(preview_rows) < payload.preview_limit:
            preview_rows.append(normalized)

    return {
        "columns": columns,
        "preview_rows": preview_rows,
        "errors": [],
        "stats": stats,
    }


def _normalize_commit_record(row_no: int, data: dict[str, Any]) -> tuple[Optional[dict[str, Any]], list[str]]:
    errors: list[str] = []

    occurred_at = _parse_datetime(data.get("occurred_at"))
    if occurred_at is None:
        errors.append("发生时间无效")

    posted_date = _parse_date(data.get("posted_date")) if data.get("posted_date") else None
    tx_type = (_normalize_str(data.get("transaction_type")) or "").lower()
    direction = (_normalize_str(data.get("direction")) or _infer_direction(tx_type) or "").lower()
    amount = _parse_float_positive(data.get("amount"))

    if tx_type not in VALID_TRANSACTION_TYPES:
        errors.append("transaction_type 无效")
    if direction not in VALID_DIRECTIONS:
        errors.append("direction 无效")
    if amount is None:
        errors.append("amount 无效")

    account_id = _normalize_int(data.get("account_id"))
    if account_id is None:
        errors.append("account_id 无效")

    counterparty_account_id = _normalize_int(data.get("counterparty_account_id"))
    category_id = _normalize_int(data.get("category_id"))

    record = {
        "occurred_at": occurred_at,
        "posted_date": posted_date,
        "account_id": account_id,
        "counterparty_account_id": counterparty_account_id,
        "category_id": category_id,
        "direction": direction,
        "transaction_type": tx_type,
        "amount": amount,
        "currency": _normalize_upper_str(data.get("currency"), "CNY"),
        "merchant": _normalize_str(data.get("merchant")),
        "description": _normalize_str(data.get("description")),
        "note": _normalize_str(data.get("note")),
        "external_ref": _normalize_str(data.get("external_ref")),
        "source": "import_csv",
        "is_cleared": bool(data.get("is_cleared", False)),
    }

    if errors:
        return None, errors
    return record, []


def commit_import(db: Session, role: str, payload) -> dict:
    owner_role = owner_role_for_create(role)
    seen_keys: set[tuple] = set()

    created_count = 0
    skipped_duplicate_count = 0
    skipped_invalid_count = 0
    failed_count = 0
    created_ids: list[int] = []
    error_rows: list[dict[str, Any]] = []
    rule_hit_rows = 0
    rule_counter: dict[str, int] = {}

    for idx, item in enumerate(payload.records, start=1):
        row_no = int(item.get("row_no") or idx)
        preview_status = str(item.get("status") or "").strip().lower()
        if preview_status == "invalid" and payload.skip_invalid:
            skipped_invalid_count += 1
            continue

        source_record = item.get("record") if isinstance(item.get("record"), dict) else item
        record, normalize_errors = _normalize_commit_record(row_no, source_record)
        if normalize_errors or record is None:
            if payload.skip_invalid:
                skipped_invalid_count += 1
            else:
                failed_count += 1
            error_rows.append({"row_no": row_no, "errors": normalize_errors})
            continue

        if payload.apply_rules:
            applied = rule_service.apply_rules_to_transaction(db, role=role, tx_like_payload=record, owner_role=owner_role)
            record = applied["payload"]
            if applied["matched_rule_ids"]:
                rule_hit_rows += 1
                for rule_name in applied["matched_rule_names"]:
                    rule_counter[rule_name] = rule_counter.get(rule_name, 0) + 1

        try:
            transaction_service._validate_business_rules(db, record, role, owner_role=owner_role)
        except AppError as exc:
            if payload.skip_invalid:
                skipped_invalid_count += 1
            else:
                failed_count += 1
            error_rows.append({"row_no": row_no, "errors": [exc.message]})
            continue

        dup_key = _to_duplicate_key(owner_role, record)
        duplicate_hit = dup_key in seen_keys or _is_duplicate(db, owner_role, record)
        if duplicate_hit and payload.skip_duplicates:
            skipped_duplicate_count += 1
            continue
        seen_keys.add(dup_key)

        try:
            with db.begin_nested():
                row = LedgerTransaction(**record, owner_role=owner_role)
                db.add(row)
                db.flush()
                created_count += 1
                if len(created_ids) < 200:
                    created_ids.append(int(row.id))
        except Exception as exc:
            failed_count += 1
            error_rows.append({"row_no": row_no, "errors": [str(exc)]})
            continue

    db.commit()
    return {
        "created_count": created_count,
        "skipped_duplicate_count": skipped_duplicate_count,
        "skipped_invalid_count": skipped_invalid_count,
        "failed_count": failed_count,
        "created_ids": created_ids,
        "error_rows": error_rows,
        "rule_hit_rows": rule_hit_rows,
        "per_rule_hit_summary": rule_counter,
    }


def _template_item(row: LedgerImportTemplate) -> dict:
    mapping = {}
    apply_rules = True
    try:
        raw = json.loads(row.mapping_json or "{}")
        if isinstance(raw, dict) and "mapping" in raw:
            mapping = raw.get("mapping") or {}
            apply_rules = bool(raw.get("apply_rules", True))
        elif isinstance(raw, dict):
            mapping = raw
    except Exception:
        mapping = {}
        apply_rules = True

    return {
        "id": row.id,
        "name": row.name,
        "delimiter": row.delimiter,
        "encoding": row.encoding,
        "mapping": mapping,
        "apply_rules": apply_rules,
        "owner_role": row.owner_role,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_import_templates(db: Session, role: str) -> dict:
    q = db.query(LedgerImportTemplate).filter(LedgerImportTemplate.is_deleted == False)  # noqa: E712
    q = apply_owner_scope(q, LedgerImportTemplate, role, owner_role=owner_role_for_create(role))
    rows = q.order_by(LedgerImportTemplate.id.desc()).all()
    return {"items": [_template_item(row) for row in rows]}


def create_import_template(db: Session, role: str, payload) -> dict:
    owner_role = owner_role_for_create(role)
    row = LedgerImportTemplate(
        name=payload.name.strip(),
        delimiter=_normalize_delimiter(payload.delimiter),
        encoding=(payload.encoding or "utf-8").strip() or "utf-8",
        mapping_json=json.dumps({"mapping": payload.mapping or {}, "apply_rules": bool(payload.apply_rules)}, ensure_ascii=False),
        owner_role=owner_role,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _template_item(row)


def delete_import_template(db: Session, role: str, template_id: int) -> dict:
    row = (
        db.query(LedgerImportTemplate)
        .filter(LedgerImportTemplate.id == template_id, LedgerImportTemplate.is_deleted == False)  # noqa: E712
        .first()
    )
    if not row:
        raise AppError("not_found", "模板不存在", status_code=404)
    ensure_row_visible(row.owner_role, role)
    row.is_deleted = True
    row.deleted_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
