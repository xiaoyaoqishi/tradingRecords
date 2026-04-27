from __future__ import annotations

import json
from typing import Any

from models import LedgerImportBatch, LedgerImportRow, LedgerMerchant, LedgerTransaction
from services.ledger.constants import COMMIT_ELIGIBLE_REVIEW_STATUSES, COMMITTED_REVIEW_STATUS, INVALID_REVIEW_STATUS


def build_transaction_from_row(tx: LedgerTransaction, batch: LedgerImportBatch, row: LedgerImportRow) -> LedgerTransaction:
    tx.batch_id = batch.id
    tx.import_row_id = row.id
    tx.account_id = row.account_id
    tx.occurred_at = row.occurred_at
    tx.amount = float(row.amount)
    tx.direction = row.direction
    tx.balance = row.balance
    tx.source_channel = row.source_channel
    tx.txn_kind = row.txn_kind
    tx.scene_candidate = row.scene_candidate
    tx.platform = row.platform
    tx.merchant_raw = row.merchant_raw
    tx.merchant_normalized = row.merchant_normalized
    tx.merchant_id = row.merchant_id
    tx.description = row.raw_text
    tx.normalized_text = row.normalized_text
    tx.text_fingerprint = row.text_fingerprint
    tx.category_id = row.category_id
    tx.subcategory_id = row.subcategory_id
    tx.duplicate_key = row.duplicate_key
    tx.confidence_score = float(row.confidence or 0.0)
    tx.review_note = row.review_note
    tx.owner_role = batch.owner_role
    return tx


def sync_existing_transaction_linkage(tx: LedgerTransaction, batch: LedgerImportBatch, row: LedgerImportRow) -> LedgerTransaction:
    tx.batch_id = batch.id
    tx.import_row_id = row.id
    tx.owner_role = batch.owner_role
    return tx


def commit_rows(
    batch: LedgerImportBatch,
    rows: list[LedgerImportRow],
    existing_transactions_by_row_id: dict[int, LedgerTransaction] | None = None,
) -> dict[str, Any]:
    created_count = 0
    skipped_count = 0
    failed_count = 0
    errors: list[dict[str, Any]] = []
    transactions: list[LedgerTransaction] = []
    committed_row_ids: list[int] = []
    idempotent_row_ids: list[int] = []
    existing_map = existing_transactions_by_row_id or {}

    for row in rows:
        status = str(row.review_status or "").strip().lower()
        if status not in COMMIT_ELIGIBLE_REVIEW_STATUSES:
            skipped_count += 1
            continue

        existing = existing_map.get(int(row.id))
        if existing:
            sync_existing_transaction_linkage(existing, batch, row)
            row.review_status = COMMITTED_REVIEW_STATUS
            skipped_count += 1
            idempotent_row_ids.append(int(row.id))
            continue

        if not row.occurred_at or row.amount is None or not row.direction:
            row.review_status = INVALID_REVIEW_STATUS
            failed_count += 1
            errors.append(
                {
                    "row_id": int(row.id),
                    "error": "missing_required_fields",
                    "message": "occurred_at、amount、direction 缺失，无法提交",
                }
            )
            continue

        tx = build_transaction_from_row(LedgerTransaction(), batch, row)
        row.review_status = COMMITTED_REVIEW_STATUS
        created_count += 1
        transactions.append(tx)
        committed_row_ids.append(int(row.id))

    return {
        "created_count": created_count,
        "committed_count": created_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "errors": errors,
        "transactions": transactions,
        "committed_row_ids": committed_row_ids,
        "idempotent_row_ids": idempotent_row_ids,
    }


def upsert_merchant_from_rows(
    owner_role: str,
    rows: list[LedgerImportRow],
    existing: list[LedgerMerchant],
    counted_row_ids: set[int] | None = None,
    sync_row_ids: set[int] | None = None,
) -> list[LedgerMerchant]:
    merchant_map: dict[str, LedgerMerchant] = {x.canonical_name: x for x in existing if x.canonical_name}
    touched: list[LedgerMerchant] = []
    counted_ids = counted_row_ids or set()
    sync_ids = sync_row_ids or counted_ids

    for row in rows:
        if row.review_status != COMMITTED_REVIEW_STATUS or int(row.id) not in sync_ids:
            continue
        canonical = (row.merchant_normalized or row.merchant_raw or "").strip()
        if not canonical:
            continue

        record = merchant_map.get(canonical)
        if not record:
            aliases = [row.merchant_raw] if row.merchant_raw and row.merchant_raw != canonical else []
            record = LedgerMerchant(
                canonical_name=canonical,
                aliases_json=json.dumps(aliases, ensure_ascii=False),
                hit_count=0,
                owner_role=owner_role,
            )
            merchant_map[canonical] = record
        if int(row.id) in counted_ids:
            record.hit_count = int(record.hit_count or 0) + 1
        if row.category_id and not record.default_category_id:
            record.default_category_id = row.category_id
        if row.subcategory_id and not record.default_subcategory_id:
            record.default_subcategory_id = row.subcategory_id
        if record.id:
            row.merchant_id = record.id
        touched.append(record)

    return list({id(x): x for x in touched}.values())
