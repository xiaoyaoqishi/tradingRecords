from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.config import settings
from core.errors import AppError
from models import LedgerCategory, LedgerImportBatch, LedgerImportRow, LedgerMerchant, LedgerRule, LedgerTransaction
from services.ledger import apply_owner_scope, ensure_row_visible, owner_role_for_create
from services.ledger.imports.deduper import build_duplicate_key, classify_duplicate
from services.ledger.imports.normalizers import normalize_row_payload
from services.ledger.imports.parsers import decode_bytes, parse_rows
from services.ledger.imports.profiles import detect_source_type, detect_source_type_by_columns
from services.ledger.review.bulk_apply import commit_rows, upsert_merchant_from_rows
from services.ledger.review.queue import row_to_item
from services.ledger.rules.engine import classify_rows, rule_to_item

IMPORT_DIR = settings.data_dir / "ledger_imports"
IMPORT_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_CHANNEL_DISPLAY = {
    "wechat": "微信",
    "alipay": "支付宝",
    "meituan": "美团",
    "jd": "京东",
    "pinduoduo": "拼多多",
    "bank_card": "银行卡",
    "other": "其他",
    "transfer": "转账",
    "repayment": "还款",
    "refund": "退款",
    "income": "收入",
    "fee": "手续费",
    "unknown": "未识别",
    "unkonwn": "其他",
}

PLATFORM_DISPLAY = {
    "wechat_pay": "微信支付",
    "wechat": "微信",
    "alipay": "支付宝",
    "meituan_pay": "美团支付",
    "meituan": "美团",
    "jd": "京东",
    "pinduoduo": "拼多多",
    "taobao": "淘宝",
    "tmall": "天猫",
    "bank_card": "银行卡",
    "other": "其他",
    "unknown": "未识别",
    "unkonwn": "其他",
}


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _batch_to_item(row: LedgerImportBatch) -> dict[str, Any]:
    source_type = row.source_type
    return {
        "id": row.id,
        "source_type": source_type,
        "source_type_display": SOURCE_CHANNEL_DISPLAY.get(source_type, source_type or "未识别"),
        "file_name": row.file_name,
        "file_hash": row.file_hash,
        "status": row.status,
        "total_rows": int(row.total_rows or 0),
        "parsed_rows": int(row.parsed_rows or 0),
        "matched_rows": int(row.matched_rows or 0),
        "review_rows": int(row.review_rows or 0),
        "duplicate_rows": int(row.duplicate_rows or 0),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _build_parse_diagnostics(db: Session, batch_id: int) -> dict[str, Any]:
    rows = db.query(LedgerImportRow).filter(LedgerImportRow.batch_id == batch_id).order_by(LedgerImportRow.row_index.asc()).limit(3).all()
    if not rows:
        return {"columns": [], "selected_columns": {}, "sample_rows": [], "raw_text_examples": []}

    columns: list[str] = []
    selected_columns: dict[str, Any] = {}
    sample_rows: list[dict[str, Any]] = []
    raw_text_examples: list[str] = []
    for row in rows:
        try:
            raw = json.loads(row.raw_payload_json or "{}")
        except Exception:
            raw = {}
        try:
            trace = json.loads(row.execution_trace_json or "{}")
        except Exception:
            trace = {}
        parse_debug = (trace or {}).get("parse", {})
        if not columns:
            columns = list(raw.keys())
        if parse_debug and not selected_columns:
            selected_columns = parse_debug.get("selected_columns") or {}
        sample_rows.append(raw)
        if row.raw_text:
            raw_text_examples.append(str(row.raw_text))
    return {
        "columns": columns,
        "selected_columns": selected_columns,
        "sample_rows": sample_rows[:3],
        "raw_text_examples": raw_text_examples[:3],
    }


def _resolve_batch(db: Session, role: str, batch_id: int) -> LedgerImportBatch:
    row = db.query(LedgerImportBatch).filter(LedgerImportBatch.id == batch_id).first()
    if not row:
        raise AppError("not_found", "导入批次不存在", status_code=404)
    ensure_row_visible(row.owner_role, role)
    return row


def _resolve_rows(db: Session, role: str, batch: LedgerImportBatch, row_ids: list[int]) -> list[LedgerImportRow]:
    if not row_ids:
        raise AppError("invalid_row_ids", "row_ids 不能为空", status_code=400)
    q = db.query(LedgerImportRow).filter(LedgerImportRow.batch_id == batch.id, LedgerImportRow.id.in_(row_ids))
    rows = q.all()
    if len(rows) != len(set(row_ids)):
        raise AppError("invalid_row_ids", "存在无效 row_id", status_code=400)
    return rows


def _resolve_rule(db: Session, role: str, rule_id: int) -> LedgerRule:
    row = db.query(LedgerRule).filter(
        LedgerRule.id == rule_id,
        LedgerRule.is_deleted == False,  # noqa: E712
    ).first()
    if not row:
        raise AppError("not_found", "规则不存在", status_code=404)
    ensure_row_visible(row.owner_role, role)
    return row


def _text_match(mode: str, pattern: str, text: str) -> bool:
    mode_value = (mode or "contains").strip().lower()
    pattern_value = (pattern or "").strip()
    source = text or ""
    if not pattern_value:
        return False
    if mode_value == "exact":
        return source == pattern_value
    if mode_value == "prefix":
        return source.startswith(pattern_value)
    if mode_value == "regex":
        try:
            import re

            return re.search(pattern_value, source) is not None
        except Exception:
            return False
    return pattern_value in source


def _normalize_source_platform_value(value: Any) -> Optional[str]:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    alias_map = {
        "wechat_pay": "wechat",
        "alipay_pay": "alipay",
        "meituan_pay": "meituan",
        "bank": "bank_card",
        "others": "other",
        "other_platform": "other",
        "other_channel": "other",
        "unkonwn": "other",
    }
    normalized = alias_map.get(raw, raw)
    return normalized


def _rule_matches_row(rule: LedgerRule, row: LedgerImportRow) -> bool:
    if rule.source_channel_condition and (row.source_channel or "") != rule.source_channel_condition:
        return False
    if rule.platform_condition and (row.platform or "") != rule.platform_condition:
        return False
    if rule.direction_condition and (row.direction or "") != rule.direction_condition:
        return False
    if rule.amount_min is not None and (row.amount is None or float(row.amount) < float(rule.amount_min)):
        return False
    if rule.amount_max is not None and (row.amount is None or float(row.amount) > float(rule.amount_max)):
        return False
    text = (row.normalized_text or row.raw_text or "").strip()
    return _text_match(rule.match_mode, rule.pattern, text)


def _is_unrecognized_row(row: LedgerImportRow) -> bool:
    return (not row.source_channel) or (not row.merchant_normalized) or (not row.category_id)


def _resolve_category_ids_by_name(
    db: Session,
    owner_role: str,
    target_category_name: Optional[str],
    target_subcategory_name: Optional[str],
) -> tuple[Optional[int], Optional[int]]:
    category_id: Optional[int] = None
    subcategory_id: Optional[int] = None
    if target_category_name:
        category = db.query(LedgerCategory).filter(
            LedgerCategory.owner_role == owner_role,
            LedgerCategory.name == target_category_name.strip(),
            LedgerCategory.parent_id.is_(None),
            LedgerCategory.is_deleted == False,  # noqa: E712
        ).first()
        if not category:
            category = LedgerCategory(
                owner_role=owner_role,
                parent_id=None,
                name=target_category_name.strip(),
                category_type="expense",
                sort_order=999,
                is_active=True,
            )
            db.add(category)
            db.flush()
        category_id = int(category.id)
    if target_subcategory_name:
        q = db.query(LedgerCategory).filter(
            LedgerCategory.owner_role == owner_role,
            LedgerCategory.name == target_subcategory_name.strip(),
            LedgerCategory.is_deleted == False,  # noqa: E712
        )
        if category_id:
            q = q.filter(LedgerCategory.parent_id == category_id)
        subcategory = q.first()
        if not subcategory:
            raise AppError("invalid_subcategory", f"目标子分类不存在：{target_subcategory_name}", status_code=400)
        subcategory_id = int(subcategory.id)
        if not category_id and subcategory.parent_id:
            category_id = int(subcategory.parent_id)
    return category_id, subcategory_id


def _guess_match_text(rows: list[LedgerImportRow]) -> str:
    if not rows:
        return ""
    candidates: list[str] = []
    for row in rows:
        for value in [row.merchant_raw, row.merchant_normalized]:
            text = (value or "").strip()
            if text and text not in {"未识别", "未知商户"}:
                candidates.append(text)
        raw = (row.raw_text or "").strip()
        if raw:
            tail = raw.split("-")[-1].strip()
            if " " in tail:
                tail = tail.split(" ")[0].strip()
            if tail:
                candidates.append(tail)
    if not candidates:
        return ""
    stats: dict[str, int] = defaultdict(int)
    for item in candidates:
        stats[item] += 1
    return sorted(stats.items(), key=lambda x: (x[1], len(x[0])), reverse=True)[0][0]


def _guess_target_merchant(rows: list[LedgerImportRow], match_text: str) -> str:
    candidates: list[str] = []
    for row in rows:
        for value in [row.merchant_normalized, row.merchant_raw]:
            text = (value or "").strip()
            if text and text not in {"未识别", "未知商户"}:
                candidates.append(text)
    if candidates:
        stats: dict[str, int] = defaultdict(int)
        for item in candidates:
            stats[item] += 1
        return sorted(stats.items(), key=lambda x: (x[1], len(x[0])), reverse=True)[0][0]
    return (match_text or "").strip()


def _count_unrecognized(rows: list[LedgerImportRow]) -> int:
    return sum(1 for row in rows if _is_unrecognized_row(row))


def _normalize_aliases(raw_aliases: Any) -> list[str]:
    aliases = raw_aliases if isinstance(raw_aliases, list) else []
    out: list[str] = []
    seen: set[str] = set()
    for item in aliases:
        value = str(item or "").strip()
        key = value.lower()
        if not value or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _merchant_item_with_recent_rows(db: Session, row: LedgerMerchant, limit: int = 3) -> dict[str, Any]:
    try:
        aliases = json.loads(row.aliases_json or "[]")
    except Exception:
        aliases = []
    try:
        tags = json.loads(row.tags_json or "[]")
    except Exception:
        tags = []

    samples = db.query(LedgerImportRow).filter(
        LedgerImportRow.owner_role == row.owner_role,
        LedgerImportRow.merchant_normalized == row.canonical_name,
    ).order_by(LedgerImportRow.id.desc()).limit(limit).all()
    recent_rows = [
        {
            "id": int(x.id),
            "batch_id": int(x.batch_id),
            "occurred_at": x.occurred_at,
            "amount": float(x.amount or 0),
            "raw_text": x.raw_text,
            "merchant_raw": x.merchant_raw,
            "category_id": x.category_id,
        }
        for x in samples
    ]

    return {
        "id": row.id,
        "canonical_name": row.canonical_name,
        "aliases": aliases,
        "default_category_id": row.default_category_id,
        "default_subcategory_id": row.default_subcategory_id,
        "tags": tags,
        "hit_count": int(row.hit_count or 0),
        "recent_rows": recent_rows,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }

def create_import_batch(db: Session, role: str, file_name: str, file_bytes: bytes) -> dict[str, Any]:
    owner_role = owner_role_for_create(role)
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    sample_text = ""
    try:
        sample_text = decode_bytes(file_bytes[:4096])
    except Exception:
        sample_text = ""

    source_type = detect_source_type(file_name, sample_text)
    file_token = f"{uuid.uuid4().hex}_{Path(file_name).name}"
    file_path = IMPORT_DIR / file_token
    file_path.write_bytes(file_bytes)

    batch = LedgerImportBatch(
        source_type=source_type,
        file_name=Path(file_name).name,
        file_hash=file_hash,
        file_path=str(file_path),
        status="uploaded",
        owner_role=owner_role,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return _batch_to_item(batch)


def list_import_batches(db: Session, role: str) -> dict[str, Any]:
    owner_role = owner_role_for_create(role)
    q = db.query(LedgerImportBatch)
    q = apply_owner_scope(q, LedgerImportBatch, role, owner_role=owner_role)
    rows = q.order_by(LedgerImportBatch.id.desc()).all()
    return {"items": [_batch_to_item(x) for x in rows], "total": len(rows)}


def get_import_batch(db: Session, role: str, batch_id: int) -> dict[str, Any]:
    row = _resolve_batch(db, role, batch_id)
    payload = _batch_to_item(row)
    payload["parse_diagnostics"] = _build_parse_diagnostics(db, row.id)
    return payload


def delete_import_batch(db: Session, role: str, batch_id: int) -> dict[str, Any]:
    batch = _resolve_batch(db, role, batch_id)

    file_path = Path(batch.file_path or "")
    row_ids = [
        int(x.id)
        for x in db.query(LedgerImportRow.id).filter(LedgerImportRow.batch_id == batch.id).all()
    ]

    if row_ids:
        db.query(LedgerTransaction).filter(
            or_(
                LedgerTransaction.batch_id == batch.id,
                LedgerTransaction.import_row_id.in_(row_ids),
            )
        ).delete(synchronize_session=False)

    db.query(LedgerImportRow).filter(LedgerImportRow.batch_id == batch.id).delete(synchronize_session=False)
    db.delete(batch)
    db.commit()

    if file_path and file_path.exists():
        try:
            file_path.unlink()
        except Exception:
            pass

    return {"deleted": True, "batch_id": batch_id}


def parse_import_batch(db: Session, role: str, batch_id: int) -> dict[str, Any]:
    batch = _resolve_batch(db, role, batch_id)
    file_path = Path(batch.file_path)
    if not file_path.exists():
        raise AppError("batch_file_not_found", "导入文件不存在", status_code=404)

    raw_bytes = file_path.read_bytes()
    rows = parse_rows(raw_bytes, batch.file_name)
    detected_from_cols = detect_source_type_by_columns(batch.file_name, list(rows[0].keys()) if rows else [])
    if detected_from_cols != "unknown":
        batch.source_type = detected_from_cols

    db.query(LedgerImportRow).filter(LedgerImportRow.batch_id == batch.id).delete()

    parsed_rows = 0
    selected_columns_summary: dict[str, Any] = {}
    for idx, raw in enumerate(rows, start=1):
        normalized, parse_debug = normalize_row_payload(raw, batch.source_type)
        if not selected_columns_summary and parse_debug.get("selected_columns"):
            selected_columns_summary = parse_debug.get("selected_columns") or {}
        duplicate_key = build_duplicate_key(
            account_id=normalized.get("account_id"),
            occurred_at=normalized.get("occurred_at"),
            amount=normalized.get("amount"),
            direction=normalized.get("direction"),
            merchant_normalized=normalized.get("merchant_raw"),
            text_fingerprint=normalized.get("text_fingerprint"),
        )
        row = LedgerImportRow(
            batch_id=batch.id,
            row_index=idx,
            account_id=normalized.get("account_id"),
            raw_payload_json=_json_dump(raw),
            raw_text=normalized.get("raw_text"),
            normalized_text=normalized.get("normalized_text"),
            text_fingerprint=normalized.get("text_fingerprint"),
            occurred_at=normalized.get("occurred_at"),
            occurred_bucket=normalized.get("occurred_bucket"),
            amount=normalized.get("amount"),
            direction=normalized.get("direction"),
            balance=normalized.get("balance"),
            source_channel=normalized.get("source_channel"),
            platform=normalized.get("platform"),
            merchant_raw=normalized.get("merchant_raw"),
            duplicate_key=duplicate_key,
            review_status="pending",
            owner_role=batch.owner_role,
            execution_trace_json=_json_dump(
                {
                    "parse": {
                        "source_type": batch.source_type,
                        "selected_columns": parse_debug.get("selected_columns") or {},
                        "raw_text_parts": parse_debug.get("raw_text_parts") or [],
                    }
                }
            ),
        )
        db.add(row)
        parsed_rows += 1

    batch.total_rows = len(rows)
    batch.parsed_rows = parsed_rows
    batch.status = "parsed"
    batch.matched_rows = 0
    batch.review_rows = parsed_rows
    batch.duplicate_rows = 0

    db.commit()
    db.refresh(batch)
    payload = _batch_to_item(batch)
    payload["parse_diagnostics"] = {
        "columns": list(rows[0].keys()) if rows else [],
        "selected_columns": selected_columns_summary,
        "sample_rows": rows[:3],
        "raw_text_examples": [x.raw_text for x in db.query(LedgerImportRow).filter(LedgerImportRow.batch_id == batch.id).order_by(LedgerImportRow.row_index.asc()).limit(3).all() if x.raw_text],
    }
    return payload


def classify_import_batch(db: Session, role: str, batch_id: int) -> dict[str, Any]:
    batch = _resolve_batch(db, role, batch_id)

    rows = db.query(LedgerImportRow).filter(LedgerImportRow.batch_id == batch.id).order_by(LedgerImportRow.row_index.asc()).all()
    if not rows:
        raise AppError("empty_batch", "当前批次没有可分类的行，请先解析", status_code=400)

    result = classify_rows(db, role, batch.owner_role, rows)

    batch.matched_rows = int(result.get("matched_rows", 0))
    batch.review_rows = int(result.get("review_rows", 0))
    batch.status = "classified"

    db.commit()
    db.refresh(batch)
    return _batch_to_item(batch)


def reprocess_import_batch(db: Session, role: str, batch_id: int) -> dict[str, Any]:
    batch = _resolve_batch(db, role, batch_id)
    rows = db.query(LedgerImportRow).filter(LedgerImportRow.batch_id == batch.id).order_by(LedgerImportRow.row_index.asc()).all()
    if not rows:
        raise AppError("empty_batch", "当前批次没有可重算的行，请先解析", status_code=400)

    result = classify_rows(db, role, batch.owner_role, rows)
    batch.matched_rows = int(result.get("matched_rows", 0))
    batch.review_rows = int(result.get("review_rows", 0))
    batch.status = "classified"
    db.commit()

    return dedupe_import_batch(db, role=role, batch_id=batch_id)


def _basis_for_row(row: LedgerImportRow) -> dict[str, Any]:
    account = row.account_id or 0
    amount = f"{float(row.amount or 0):.2f}"
    direction = (row.direction or "").lower()
    merchant = (row.merchant_normalized or row.merchant_raw or "").strip().lower()
    occurred_bucket = row.occurred_bucket or ""
    fp = row.text_fingerprint or ""
    exact_key = f"{account}|{occurred_bucket}|{amount}|{direction}|{merchant}|{fp}"
    probable_key = f"{account}|{amount}|{direction}|{merchant}|{fp}"
    review_key = f"{amount}|{direction}|{fp}"
    return {
        "account_id": account,
        "occurred_bucket": occurred_bucket,
        "amount": amount,
        "direction": direction,
        "merchant_normalized": merchant,
        "text_fingerprint": fp,
        "exact_key": exact_key,
        "probable_key": probable_key,
        "review_key": review_key,
    }


def dedupe_import_batch(db: Session, role: str, batch_id: int) -> dict[str, Any]:
    batch = _resolve_batch(db, role, batch_id)
    rows = db.query(LedgerImportRow).filter(LedgerImportRow.batch_id == batch.id).order_by(LedgerImportRow.row_index.asc()).all()
    if not rows:
        raise AppError("empty_batch", "当前批次没有可去重的行", status_code=400)

    # 用户指定：关闭去重能力，避免同商户多次消费被误判为重复。
    for row in rows:
        row.duplicate_type = None
        row.duplicate_score = 0.0
        row.duplicate_basis_json = _json_dump({})
        if row.review_status == "duplicate":
            row.review_status = "pending"

    batch.duplicate_rows = 0
    batch.review_rows = db.query(LedgerImportRow.id).filter(
        LedgerImportRow.batch_id == batch.id,
        LedgerImportRow.review_status.in_(["pending", "confirmed"]),
    ).count()
    batch.status = "deduped"

    db.commit()
    db.refresh(batch)
    return _batch_to_item(batch)


def list_review_rows(db: Session, role: str, batch_id: int, status: Optional[str] = None) -> dict[str, Any]:
    batch = _resolve_batch(db, role, batch_id)
    q = db.query(LedgerImportRow).filter(LedgerImportRow.batch_id == batch.id)
    if status:
        q = q.filter(LedgerImportRow.review_status == status)
    else:
        q = q.filter(LedgerImportRow.review_status.in_(["pending", "confirmed", "duplicate", "invalid"]))

    rows = q.order_by(LedgerImportRow.row_index.asc()).all()
    category_ids = {int(x.category_id) for x in rows if x.category_id}
    category_name_map: dict[int, str] = {}
    if category_ids:
        for c in db.query(LedgerCategory).filter(
            LedgerCategory.id.in_(list(category_ids)),
            LedgerCategory.is_deleted == False,  # noqa: E712
        ).all():
            category_name_map[int(c.id)] = c.name

    items: list[dict[str, Any]] = []
    for x in rows:
        item = row_to_item(x)
        source_value = str(item.get("source_channel") or "").strip()
        platform_value = str(item.get("platform") or "").strip()
        category_id = item.get("category_id")
        item["source_channel_display"] = SOURCE_CHANNEL_DISPLAY.get(source_value, source_value or "未识别")
        item["platform_display"] = PLATFORM_DISPLAY.get(platform_value, platform_value or "未识别")
        item["category_name"] = category_name_map.get(int(category_id), None) if category_id else None
        items.append(item)
    return {"items": items, "total": len(rows)}


def get_review_insights(db: Session, role: str, batch_id: int) -> dict[str, Any]:
    batch = _resolve_batch(db, role, batch_id)
    rows = db.query(LedgerImportRow).filter(
        LedgerImportRow.batch_id == batch.id,
        LedgerImportRow.review_status.in_(["pending", "confirmed", "invalid"]),
    ).all()

    merchant_group: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "amount_sum": 0.0, "row_ids": []})
    text_group: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "amount_sum": 0.0, "row_ids": []})
    for row in rows:
        if not _is_unrecognized_row(row):
            continue
        merchant_key = (row.merchant_raw or row.merchant_normalized or "未识别商户").strip() or "未识别商户"
        text_key = (row.raw_text or row.normalized_text or "未识别摘要").strip() or "未识别摘要"
        amount = abs(float(row.amount or 0))

        merchant_group[merchant_key]["count"] += 1
        merchant_group[merchant_key]["amount_sum"] += amount
        merchant_group[merchant_key]["row_ids"].append(int(row.id))

        text_group[text_key]["count"] += 1
        text_group[text_key]["amount_sum"] += amount
        text_group[text_key]["row_ids"].append(int(row.id))

    def _to_top_items(group_map: dict[str, dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
        items = []
        for key, stat in group_map.items():
            items.append(
                {
                    "key": key,
                    "count": int(stat["count"]),
                    "amount_sum": round(float(stat["amount_sum"]), 2),
                    "row_ids": stat["row_ids"][:100],
                }
            )
        return sorted(items, key=lambda x: (x["count"], x["amount_sum"]), reverse=True)[:limit]

    return {
        "unresolved_merchants_top": _to_top_items(merchant_group),
        "unresolved_raw_text_top": _to_top_items(text_group),
    }


def review_bulk_set_category(db: Session, role: str, batch_id: int, payload) -> dict[str, Any]:
    batch = _resolve_batch(db, role, batch_id)
    rows = _resolve_rows(db, role, batch, payload.row_ids)
    updated = 0
    for row in rows:
        if row.review_status == "duplicate":
            continue
        row.category_id = int(payload.category_id)
        row.subcategory_id = int(payload.subcategory_id) if payload.subcategory_id else None
        row.review_status = "pending"
        row.review_note = "批量修正分类"
        updated += 1
    db.commit()
    return {"updated_count": updated}


def review_bulk_set_merchant(db: Session, role: str, batch_id: int, payload) -> dict[str, Any]:
    batch = _resolve_batch(db, role, batch_id)
    rows = _resolve_rows(db, role, batch, payload.row_ids)
    updated = 0
    merchant_name = payload.merchant_normalized.strip()

    merchant = db.query(LedgerMerchant).filter(
        LedgerMerchant.owner_role == batch.owner_role,
        LedgerMerchant.canonical_name == merchant_name,
        LedgerMerchant.is_deleted == False,  # noqa: E712
    ).first()
    if not merchant:
        merchant = LedgerMerchant(canonical_name=merchant_name, aliases_json="[]", tags_json="[]", owner_role=batch.owner_role)
        db.add(merchant)
        db.flush()

    for row in rows:
        if row.review_status == "duplicate":
            continue
        row.merchant_normalized = merchant_name
        row.merchant_id = merchant.id
        row.review_status = "pending"
        row.review_note = "批量修正商户"
        updated += 1
    db.commit()
    return {"updated_count": updated}


def review_bulk_confirm(db: Session, role: str, batch_id: int, payload) -> dict[str, Any]:
    batch = _resolve_batch(db, role, batch_id)
    rows = _resolve_rows(db, role, batch, payload.row_ids)
    updated = 0
    for row in rows:
        if row.review_status in {"duplicate", "invalid", "committed"}:
            continue
        row.review_status = "confirmed"
        row.review_note = (row.review_note or "") + ("; " if row.review_note else "") + "人工确认"
        updated += 1
    db.commit()
    return {"updated_count": updated}


def review_reclassify_pending(db: Session, role: str, batch_id: int) -> dict[str, Any]:
    batch = _resolve_batch(db, role, batch_id)
    rows = db.query(LedgerImportRow).filter(
        LedgerImportRow.batch_id == batch.id,
        LedgerImportRow.review_status == "pending",
    ).order_by(LedgerImportRow.row_index.asc()).all()
    if not rows:
        return {"reclassified_count": 0, "matched_rows": 0, "review_rows": 0}

    result = classify_rows(db, role, batch.owner_role, rows)
    db.commit()
    return {
        "reclassified_count": len(rows),
        "matched_rows": int(result.get("matched_rows", 0)),
        "review_rows": int(result.get("review_rows", 0)),
    }


def review_generate_rule(db: Session, role: str, batch_id: int, payload) -> dict[str, Any]:
    batch = _resolve_batch(db, role, batch_id)
    rows = _resolve_rows(db, role, batch, payload.row_ids)
    all_rows = db.query(LedgerImportRow).filter(LedgerImportRow.batch_id == batch.id).order_by(LedgerImportRow.row_index.asc()).all()
    unrecognized_before = _count_unrecognized(all_rows)

    apply_scope = (payload.apply_scope or "global").strip().lower()
    if apply_scope not in {"global", "profile"}:
        raise AppError("invalid_scope", "apply_scope 仅支持 global 或 profile", status_code=400)

    rule_kind = ((payload.rule_kind or payload.rule_type or "merchant").strip().lower())
    if rule_kind not in {"merchant", "category", "merchant_and_category", "source"}:
        raise AppError("invalid_rule_kind", "rule_kind 仅支持 merchant/category/merchant_and_category/source", status_code=400)

    match_text = (payload.match_text or _guess_match_text(rows)).strip()
    if not match_text:
        raise AppError("invalid_match_text", "无法从样本中提取匹配关键词，请手动填写", status_code=400)

    target_merchant = (payload.target_merchant_name or _guess_target_merchant(rows, match_text)).strip() or None
    target_platform = _normalize_source_platform_value(payload.target_platform or payload.target_source_channel)

    scope_source = None
    scope_platform = None
    if apply_scope == "profile":
        for row in rows:
            if row.source_channel and not scope_source:
                scope_source = row.source_channel
            if row.platform and not scope_platform:
                scope_platform = row.platform
        if not scope_source and not scope_platform:
            scope_source = batch.source_type if batch.source_type != "unknown" else None

    target_category_id, target_subcategory_id = _resolve_category_ids_by_name(
        db,
        owner_role=batch.owner_role,
        target_category_name=payload.target_category_name,
        target_subcategory_name=payload.target_subcategory_name,
    )
    if rule_kind in {"category", "merchant_and_category"} and not (target_category_id or payload.target_category_id):
        raise AppError("invalid_category", "分类规则必须选择目标分类", status_code=400)
    if rule_kind == "source" and not target_platform:
        raise AppError("invalid_platform", "来源/平台规则必须选择目标平台", status_code=400)
    if payload.target_category_id and not target_category_id:
        target_category_id = int(payload.target_category_id)
    if payload.target_subcategory_id and not target_subcategory_id:
        target_subcategory_id = int(payload.target_subcategory_id)

    owner_rules = db.query(LedgerRule).filter(
        LedgerRule.owner_role == batch.owner_role,
        LedgerRule.is_deleted == False,  # noqa: E712
    ).all()

    def _same_scope(existing: LedgerRule, candidate: dict[str, Any]) -> bool:
        return (
            (existing.source_channel_condition or "") == (candidate.get("source_channel_condition") or "")
            and (existing.platform_condition or "") == (candidate.get("platform_condition") or "")
        )

    def _rule_exists(candidate: dict[str, Any]) -> bool:
        for existing in owner_rules:
            if existing.rule_type != candidate["rule_type"]:
                continue
            if (existing.pattern or "") != (candidate["pattern"] or ""):
                continue
            if (existing.target_merchant or "") != (candidate.get("target_merchant") or ""):
                continue
            if (existing.target_platform or "") != (candidate.get("target_platform") or ""):
                continue
            if int(existing.target_category_id or 0) != int(candidate.get("target_category_id") or 0):
                continue
            if int(existing.target_subcategory_id or 0) != int(candidate.get("target_subcategory_id") or 0):
                continue
            if not _same_scope(existing, candidate):
                continue
            return True
        return False

    def _has_conflict(candidate: dict[str, Any]) -> bool:
        for existing in owner_rules:
            if existing.rule_type != candidate["rule_type"]:
                continue
            if (existing.pattern or "") != (candidate["pattern"] or ""):
                continue
            if not _same_scope(existing, candidate):
                continue
            if candidate["rule_type"] == "merchant":
                if (existing.target_merchant or "") != (candidate.get("target_merchant") or ""):
                    return True
            if candidate["rule_type"] == "source":
                if (existing.target_platform or "") != (candidate.get("target_platform") or ""):
                    return True
            if candidate["rule_type"] == "category":
                if int(existing.target_category_id or 0) != int(candidate.get("target_category_id") or 0):
                    return True
        return False

    candidates: list[dict[str, Any]] = []
    if rule_kind in {"merchant", "merchant_and_category"}:
        if not target_merchant:
            raise AppError("invalid_target_merchant", "商户归一规则需要目标商户名", status_code=400)
        candidates.append(
            {
                "rule_type": "merchant",
                "priority": payload.priority,
                "enabled": True,
                "match_mode": "contains",
                "pattern": match_text,
                "target_merchant": target_merchant,
                "target_category_id": None,
                "target_subcategory_id": None,
                "explain_text": "导入校对台生成商户归一规则",
                "confidence_score": 0.92,
                "source_channel_condition": scope_source,
                "platform_condition": scope_platform,
            }
        )
    if rule_kind in {"category", "merchant_and_category"}:
        candidates.append(
            {
                "rule_type": "category",
                "priority": payload.priority,
                "enabled": True,
                "match_mode": "contains",
                "pattern": match_text,
                "target_merchant": None,
                "target_category_id": target_category_id,
                "target_subcategory_id": target_subcategory_id,
                "explain_text": "导入校对台生成分类规则",
                "confidence_score": 0.9,
                "source_channel_condition": scope_source,
                "platform_condition": scope_platform,
            }
        )
    if rule_kind == "source":
        candidates.append(
            {
                "rule_type": "source",
                "priority": payload.priority,
                "enabled": True,
                "match_mode": "contains",
                "pattern": match_text,
                "target_platform": target_platform,
                "target_merchant": None,
                "target_category_id": None,
                "target_subcategory_id": None,
                "explain_text": "导入校对台生成来源/平台规则",
                "confidence_score": 0.92,
                "source_channel_condition": scope_source,
                "platform_condition": scope_platform,
            }
        )

    preview: list[dict[str, Any]] = []
    created: list[int] = []
    skipped_existing_count = 0
    duplicate_rule_count = 0
    conflict_rule_count = 0
    matched_ids: set[int] = set()

    for candidate in candidates:
        skipped_existing = _rule_exists(candidate)
        has_conflict = _has_conflict(candidate)
        if skipped_existing:
            skipped_existing_count += 1
            duplicate_rule_count += 1
        if has_conflict:
            conflict_rule_count += 1

        shadow_rule = LedgerRule(
            rule_type=candidate["rule_type"],
            priority=int(candidate["priority"]),
            enabled=True,
            match_mode=str(candidate["match_mode"]),
            pattern=str(candidate["pattern"]),
            source_channel_condition=candidate.get("source_channel_condition"),
            platform_condition=candidate.get("platform_condition"),
            direction_condition=None,
            amount_min=None,
            amount_max=None,
            target_platform=candidate.get("target_platform"),
            target_merchant=candidate.get("target_merchant"),
            target_txn_kind=None,
            target_scene=None,
            target_category_id=candidate.get("target_category_id"),
            target_subcategory_id=candidate.get("target_subcategory_id"),
            explain_text=candidate.get("explain_text"),
            confidence_score=float(candidate.get("confidence_score") or 0.0),
            owner_role=batch.owner_role,
        )
        hit_rows = [x for x in all_rows if _rule_matches_row(shadow_rule, x)]
        for hit in hit_rows:
            matched_ids.add(int(hit.id))
        preview.append(
            {
                "row_id": int(rows[0].id),
                "rule_type": candidate["rule_type"],
                "pattern": candidate["pattern"],
                "expected_hit_rows": len(hit_rows),
                "skipped_existing": skipped_existing,
                "apply_scope": apply_scope,
                "source_channel_condition": candidate.get("source_channel_condition"),
                "platform_condition": candidate.get("platform_condition"),
                "target_merchant": candidate.get("target_merchant"),
                "target_platform": candidate.get("target_platform"),
                "target_category_id": candidate.get("target_category_id"),
                "target_subcategory_id": candidate.get("target_subcategory_id"),
            }
        )

        if payload.preview_only or skipped_existing:
            continue

        rule = LedgerRule(
            rule_type=candidate["rule_type"],
            priority=int(candidate["priority"]),
            enabled=True,
            match_mode=str(candidate["match_mode"]),
            pattern=str(candidate["pattern"]),
            source_channel_condition=candidate.get("source_channel_condition"),
            platform_condition=candidate.get("platform_condition"),
            direction_condition=None,
            amount_min=None,
            amount_max=None,
            target_platform=candidate.get("target_platform"),
            target_merchant=candidate.get("target_merchant"),
            target_txn_kind=None,
            target_scene=None,
            target_category_id=candidate.get("target_category_id"),
            target_subcategory_id=candidate.get("target_subcategory_id"),
            explain_text=candidate.get("explain_text"),
            confidence_score=float(candidate.get("confidence_score") or 0.0),
            owner_role=batch.owner_role,
        )
        db.add(rule)
        db.flush()
        owner_rules.append(rule)
        created.append(int(rule.id))

    db.commit()

    reprocess_result: dict[str, Any] = {}
    if (not payload.preview_only) and created and payload.reprocess_after_create:
        replay_scope = (payload.reprocess_scope or "unconfirmed").strip().lower()
        if replay_scope not in {"unconfirmed", "all"}:
            replay_scope = "unconfirmed"
        replay_q = db.query(LedgerImportRow).filter(LedgerImportRow.batch_id == batch.id)
        if replay_scope == "unconfirmed":
            replay_q = replay_q.filter(LedgerImportRow.review_status != "confirmed")
        replay_rows = replay_q.order_by(LedgerImportRow.row_index.asc()).all()
        replay_result = {"matched_rows": 0, "review_rows": 0}
        if replay_rows:
            replay_result = classify_rows(db, role, batch.owner_role, replay_rows)
            batch.matched_rows = int(replay_result.get("matched_rows", 0))
            batch.review_rows = db.query(LedgerImportRow.id).filter(
                LedgerImportRow.batch_id == batch.id,
                LedgerImportRow.review_status.in_(["pending", "confirmed", "invalid"]),
            ).count()
            db.commit()
        rows_after = db.query(LedgerImportRow).filter(LedgerImportRow.batch_id == batch.id).order_by(LedgerImportRow.row_index.asc()).all()
        reprocess_result = {
            "unrecognized_before": unrecognized_before,
            "unrecognized_after": _count_unrecognized(rows_after),
            "reprocessed_rows": len(replay_rows),
            "matched_rows": int(replay_result.get("matched_rows", 0)),
            "reprocess_scope": replay_scope,
        }

    category_name_map: dict[int, str] = {}
    category_ids = {int(x.category_id) for x in all_rows if x.category_id}
    if category_ids:
        for c in db.query(LedgerCategory).filter(
            LedgerCategory.id.in_(list(category_ids)),
            LedgerCategory.is_deleted == False,  # noqa: E712
        ).all():
            category_name_map[int(c.id)] = str(c.name)

    sample_rows = []
    for row in all_rows:
        if int(row.id) not in matched_ids:
            continue
        sample_rows.append(
            {
                "row_id": int(row.id),
                "occurred_at": row.occurred_at,
                "raw_text": row.raw_text,
                "merchant_raw": row.merchant_raw,
                "merchant_normalized": row.merchant_normalized,
                "category_name": category_name_map.get(int(row.category_id), None) if row.category_id else None,
            }
        )
        if len(sample_rows) >= 5:
            break

    return {
        "created_rule_ids": created,
        "skipped_existing_count": skipped_existing_count,
        "preview": preview,
        "estimated_hit_rows": len(matched_ids),
        "matched_samples": sample_rows,
        "duplicate_rule_count": duplicate_rule_count,
        "conflict_rule_count": conflict_rule_count,
        "created_rule_summaries": [
            {
                "rule_type": item.get("rule_type"),
                "pattern": item.get("pattern"),
                "target_merchant": item.get("target_merchant"),
                "target_platform": item.get("target_platform"),
                "target_category_id": item.get("target_category_id"),
                "target_subcategory_id": item.get("target_subcategory_id"),
            }
            for item in preview
        ],
        "reprocess_result": reprocess_result,
    }


def commit_import_batch(db: Session, role: str, batch_id: int) -> dict[str, Any]:
    batch = _resolve_batch(db, role, batch_id)
    rows = db.query(LedgerImportRow).filter(LedgerImportRow.batch_id == batch.id).order_by(LedgerImportRow.row_index.asc()).all()
    if not rows:
        raise AppError("empty_batch", "没有可提交的导入行", status_code=400)

    committed = commit_rows(batch, rows)
    transactions = committed["transactions"]
    for tx in transactions:
        db.add(tx)

    db.flush()
    tx_ids = [int(tx.id) for tx in transactions]

    existing_merchants = db.query(LedgerMerchant).filter(
        LedgerMerchant.owner_role == batch.owner_role,
        LedgerMerchant.is_deleted == False,  # noqa: E712
    ).all()
    touched = upsert_merchant_from_rows(batch.owner_role, rows, existing_merchants)
    for merchant in touched:
        db.add(merchant)

    batch.status = "committed"
    batch.review_rows = db.query(LedgerImportRow.id).filter(
        LedgerImportRow.batch_id == batch.id,
        LedgerImportRow.review_status.in_(["pending", "confirmed", "invalid"]),
    ).count()

    db.commit()

    return {
        "created_count": int(committed["created_count"]),
        "skipped_count": int(committed["skipped_count"]),
        "transaction_ids": tx_ids,
    }


def list_merchants(db: Session, role: str) -> dict[str, Any]:
    owner_role = owner_role_for_create(role)
    q = db.query(LedgerMerchant).filter(LedgerMerchant.is_deleted == False)  # noqa: E712
    q = apply_owner_scope(q, LedgerMerchant, role, owner_role=owner_role)
    rows = q.order_by(LedgerMerchant.hit_count.desc(), LedgerMerchant.id.asc()).all()
    items = [_merchant_item_with_recent_rows(db, row) for row in rows]
    return {"items": items, "total": len(items)}


def create_merchant(db: Session, role: str, payload) -> dict[str, Any]:
    owner_role = owner_role_for_create(role)
    canonical_name = payload.canonical_name.strip()
    aliases = _normalize_aliases(payload.aliases or [])
    if canonical_name.lower() in {x.lower() for x in aliases}:
        aliases = [x for x in aliases if x.lower() != canonical_name.lower()]
    row = LedgerMerchant(
        canonical_name=canonical_name,
        aliases_json=json.dumps(aliases, ensure_ascii=False),
        default_category_id=payload.default_category_id,
        default_subcategory_id=payload.default_subcategory_id,
        tags_json=json.dumps(payload.tags or [], ensure_ascii=False),
        hit_count=0,
        owner_role=owner_role,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _merchant_item_with_recent_rows(db, row)


def update_merchant(db: Session, role: str, merchant_id: int, payload) -> dict[str, Any]:
    row = db.query(LedgerMerchant).filter(
        LedgerMerchant.id == merchant_id,
        LedgerMerchant.is_deleted == False,  # noqa: E712
    ).first()
    if not row:
        raise AppError("not_found", "商户不存在", status_code=404)
    ensure_row_visible(row.owner_role, role)

    data = payload.model_dump(exclude_unset=True)
    canonical_name = str(data.get("canonical_name") or row.canonical_name).strip()
    if not canonical_name:
        raise AppError("invalid_payload", "canonical_name 不能为空", status_code=400)

    if "aliases" in data:
        aliases = _normalize_aliases(data.get("aliases") or [])
    else:
        try:
            aliases = _normalize_aliases(json.loads(row.aliases_json or "[]"))
        except Exception:
            aliases = []
    aliases = [x for x in aliases if x.lower() != canonical_name.lower()]

    # 同 owner_role 下 canonical_name 唯一，避免归一冲突
    duplicated = db.query(LedgerMerchant.id).filter(
        LedgerMerchant.owner_role == row.owner_role,
        LedgerMerchant.id != row.id,
        LedgerMerchant.canonical_name == canonical_name,
        LedgerMerchant.is_deleted == False,  # noqa: E712
    ).first()
    if duplicated:
        raise AppError("duplicated_merchant", "目标规范名已存在，请先合并或使用其他名称", status_code=400)

    old_name = row.canonical_name
    row.canonical_name = canonical_name
    row.aliases_json = json.dumps(aliases, ensure_ascii=False)
    if "default_category_id" in data:
        row.default_category_id = data.get("default_category_id")
    if "default_subcategory_id" in data:
        row.default_subcategory_id = data.get("default_subcategory_id")
    if "tags" in data:
        row.tags_json = json.dumps(_normalize_aliases(data.get("tags") or []), ensure_ascii=False)

    if old_name != canonical_name:
        db.query(LedgerImportRow).filter(
            LedgerImportRow.owner_role == row.owner_role,
            LedgerImportRow.merchant_normalized == old_name,
        ).update({"merchant_normalized": canonical_name}, synchronize_session=False)

    db.commit()
    db.refresh(row)
    return _merchant_item_with_recent_rows(db, row)


def list_rules(db: Session, role: str) -> dict[str, Any]:
    owner_role = owner_role_for_create(role)
    q = db.query(LedgerRule).filter(LedgerRule.is_deleted == False)  # noqa: E712
    q = apply_owner_scope(q, LedgerRule, role, owner_role=owner_role)
    rows = q.order_by(LedgerRule.priority.asc(), LedgerRule.id.asc()).all()
    rule_ids = [int(x.id) for x in rows]
    hit_counts: dict[int, int] = {}
    hit_latest: dict[int, Any] = {}
    if rule_ids:
        usage_rows = db.query(
            LedgerImportRow.source_rule_id,
            LedgerImportRow.merchant_rule_id,
            LedgerImportRow.category_rule_id,
            LedgerImportRow.updated_at,
        ).filter(
            LedgerImportRow.owner_role == owner_role,
            or_(
                LedgerImportRow.source_rule_id.in_(rule_ids),
                LedgerImportRow.merchant_rule_id.in_(rule_ids),
                LedgerImportRow.category_rule_id.in_(rule_ids),
            ),
        ).all()
        for source_rule_id, merchant_rule_id, category_rule_id, updated_at in usage_rows:
            for raw_id in (source_rule_id, merchant_rule_id, category_rule_id):
                if not raw_id:
                    continue
                rid = int(raw_id)
                hit_counts[rid] = hit_counts.get(rid, 0) + 1
                if not hit_latest.get(rid) or (updated_at and updated_at > hit_latest[rid]):
                    hit_latest[rid] = updated_at

    items = []
    for row in rows:
        item = rule_to_item(row)
        rid = int(row.id)
        item["hit_count"] = int(hit_counts.get(rid, 0))
        item["last_hit_at"] = hit_latest.get(rid)
        items.append(item)
    return {"items": items, "total": len(items)}


def create_rule(db: Session, role: str, payload) -> dict[str, Any]:
    owner_role = owner_role_for_create(role)
    row = LedgerRule(
        rule_type=payload.rule_type,
        priority=payload.priority,
        enabled=payload.enabled,
        match_mode=payload.match_mode,
        pattern=payload.pattern,
        source_channel_condition=payload.source_channel_condition,
        platform_condition=payload.platform_condition,
        direction_condition=payload.direction_condition,
        amount_min=payload.amount_min,
        amount_max=payload.amount_max,
        target_platform=payload.target_platform,
        target_merchant=payload.target_merchant,
        target_txn_kind=payload.target_txn_kind,
        target_scene=payload.target_scene,
        target_category_id=payload.target_category_id,
        target_subcategory_id=payload.target_subcategory_id,
        explain_text=payload.explain_text,
        confidence_score=payload.confidence_score,
        owner_role=owner_role,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return rule_to_item(row)


def update_rule(db: Session, role: str, rule_id: int, payload) -> dict[str, Any]:
    row = _resolve_rule(db, role, rule_id)
    data = payload.model_dump(exclude_unset=True)

    if "rule_type" in data and data["rule_type"] is not None:
        row.rule_type = str(data["rule_type"]).strip()
    if "priority" in data and data["priority"] is not None:
        row.priority = int(data["priority"])
    if "enabled" in data and data["enabled"] is not None:
        row.enabled = bool(data["enabled"])
    if "match_mode" in data and data["match_mode"] is not None:
        row.match_mode = str(data["match_mode"]).strip()
    if "pattern" in data and data["pattern"] is not None:
        row.pattern = str(data["pattern"]).strip()

    for key in (
        "source_channel_condition",
        "platform_condition",
        "direction_condition",
        "amount_min",
        "amount_max",
        "target_platform",
        "target_merchant",
        "target_txn_kind",
        "target_scene",
        "target_category_id",
        "target_subcategory_id",
        "explain_text",
        "confidence_score",
    ):
        if key in data:
            setattr(row, key, data[key])

    db.commit()
    db.refresh(row)
    return rule_to_item(row)


def delete_rule(db: Session, role: str, rule_id: int) -> dict[str, Any]:
    row = _resolve_rule(db, role, rule_id)
    row.is_deleted = True
    row.deleted_at = datetime.utcnow()
    db.commit()
    return {"deleted": True, "rule_id": rule_id}
