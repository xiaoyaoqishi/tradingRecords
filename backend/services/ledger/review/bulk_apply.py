from __future__ import annotations

import json
from typing import Any

from models import LedgerImportBatch, LedgerImportRow, LedgerMerchant, LedgerTransaction


def commit_rows(batch: LedgerImportBatch, rows: list[LedgerImportRow]) -> dict[str, Any]:
    created_count = 0
    skipped_count = 0
    transactions: list[LedgerTransaction] = []

    for row in rows:
        if row.review_status != "confirmed":
            skipped_count += 1
            continue
        if not row.occurred_at or row.amount is None or not row.direction:
            row.review_status = "invalid"
            skipped_count += 1
            continue

        tx = LedgerTransaction(
            batch_id=batch.id,
            import_row_id=row.id,
            account_id=row.account_id,
            occurred_at=row.occurred_at,
            amount=float(row.amount),
            direction=row.direction,
            balance=row.balance,
            source_channel=row.source_channel,
            txn_kind=row.txn_kind,
            scene_candidate=row.scene_candidate,
            platform=row.platform,
            merchant_raw=row.merchant_raw,
            merchant_normalized=row.merchant_normalized,
            merchant_id=row.merchant_id,
            description=row.raw_text,
            normalized_text=row.normalized_text,
            text_fingerprint=row.text_fingerprint,
            category_id=row.category_id,
            subcategory_id=row.subcategory_id,
            duplicate_key=row.duplicate_key,
            review_note=row.review_note,
            owner_role=batch.owner_role,
        )
        row.review_status = "committed"
        created_count += 1
        transactions.append(tx)

    return {
        "created_count": created_count,
        "skipped_count": skipped_count,
        "transactions": transactions,
    }


def upsert_merchant_from_rows(owner_role: str, rows: list[LedgerImportRow], existing: list[LedgerMerchant]) -> list[LedgerMerchant]:
    merchant_map: dict[str, LedgerMerchant] = {x.canonical_name: x for x in existing if x.canonical_name}
    touched: list[LedgerMerchant] = []

    for row in rows:
        if row.review_status != "committed":
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
        record.hit_count = int(record.hit_count or 0) + 1
        if row.category_id and not record.default_category_id:
            record.default_category_id = row.category_id
        if row.subcategory_id and not record.default_subcategory_id:
            record.default_subcategory_id = row.subcategory_id
        touched.append(record)

    return list({id(x): x for x in touched}.values())
