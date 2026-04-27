from __future__ import annotations

import json
from typing import Any

from models import LedgerImportRow


def _json_load(raw: str | None, fallback: Any):
    try:
        parsed = json.loads(raw or "")
        return parsed
    except Exception:
        return fallback


def row_to_item(row: LedgerImportRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "batch_id": row.batch_id,
        "row_index": row.row_index,
        "account_id": row.account_id,
        "raw_payload_json": _json_load(row.raw_payload_json, {}),
        "raw_text": row.raw_text,
        "normalized_text": row.normalized_text,
        "text_fingerprint": row.text_fingerprint,
        "occurred_at": row.occurred_at,
        "occurred_bucket": row.occurred_bucket,
        "amount": row.amount,
        "direction": row.direction,
        "balance": row.balance,
        "source_channel": row.source_channel,
        "txn_kind": row.txn_kind,
        "scene_candidate": row.scene_candidate,
        "platform": row.platform,
        "merchant_raw": row.merchant_raw,
        "merchant_normalized": row.merchant_normalized,
        "merchant_id": row.merchant_id,
        "category_id": row.category_id,
        "subcategory_id": row.subcategory_id,
        "confidence": float(row.confidence or 0.0),
        "source_rule_id": row.source_rule_id,
        "source_confidence": row.source_confidence,
        "source_explain": row.source_explain,
        "merchant_rule_id": row.merchant_rule_id,
        "merchant_confidence": row.merchant_confidence,
        "merchant_explain": row.merchant_explain,
        "category_rule_id": row.category_rule_id,
        "category_confidence": row.category_confidence,
        "category_explain": row.category_explain,
        "duplicate_key": row.duplicate_key,
        "duplicate_type": row.duplicate_type,
        "duplicate_score": row.duplicate_score,
        "duplicate_basis_json": _json_load(row.duplicate_basis_json, {}),
        "review_status": row.review_status,
        "review_note": row.review_note,
        "low_confidence_reason": row.low_confidence_reason,
        "suggested_candidates_json": _json_load(row.suggested_candidates_json, []),
        "execution_trace_json": _json_load(row.execution_trace_json, {}),
    }
