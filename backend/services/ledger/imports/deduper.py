from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any


def build_duplicate_key(
    *,
    account_id: int | None,
    occurred_at: datetime | None,
    amount: float | None,
    direction: str | None,
    merchant_normalized: str | None,
    text_fingerprint: str | None,
) -> str:
    occurred = occurred_at.strftime("%Y-%m-%d %H:%M") if occurred_at else ""
    payload = "|".join(
        [
            str(account_id or 0),
            occurred,
            f"{float(amount or 0):.2f}",
            (direction or "").lower(),
            (merchant_normalized or "").strip().lower(),
            (text_fingerprint or "").strip().lower(),
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:40]


def classify_duplicate(
    *,
    row_basis: dict[str, Any],
    in_batch_index: dict[str, dict[str, Any]],
    existing_index: dict[str, dict[str, Any]],
) -> tuple[str | None, float, dict[str, Any]]:
    key = str(row_basis.get("exact_key") or "")
    probable_key = str(row_basis.get("probable_key") or "")

    if key and (key in in_batch_index or key in existing_index):
        return (
            "exact_duplicate",
            1.0,
            {
                "matched_by": "exact",
                "matched_key": key,
                "exact_basis": row_basis,
            },
        )

    if probable_key and (probable_key in in_batch_index or probable_key in existing_index):
        return (
            "probable_duplicate",
            0.75,
            {
                "matched_by": "probable",
                "matched_key": probable_key,
                "probable_basis": row_basis,
            },
        )

    weak_tokens = [
        row_basis.get("amount"),
        row_basis.get("direction"),
        row_basis.get("text_fingerprint"),
    ]
    if all(weak_tokens) and str(row_basis.get("merchant_normalized") or "").strip() == "":
        review_key = f"{row_basis['amount']}|{row_basis['direction']}|{row_basis['text_fingerprint']}"
        if review_key in in_batch_index or review_key in existing_index:
            return (
                "review_duplicate",
                0.55,
                {
                    "matched_by": "review",
                    "matched_key": review_key,
                    "review_basis": row_basis,
                },
            )

    return None, 0.0, {}
