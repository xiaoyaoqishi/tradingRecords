from __future__ import annotations

import json

from models import LedgerMerchant


def resolve_merchant(raw_name: str | None, merchants: list[LedgerMerchant]) -> str | None:
    candidate = (raw_name or "").strip()
    if not candidate:
        return None

    lowered = candidate.lower()
    for merchant in merchants:
        canonical = (merchant.canonical_name or "").strip()
        if canonical and canonical.lower() in lowered:
            return canonical

        aliases = []
        try:
            aliases = json.loads(merchant.aliases_json or "[]")
        except Exception:
            aliases = []
        for alias in aliases:
            if str(alias).strip() and str(alias).strip().lower() in lowered:
                return canonical or candidate
    return None
