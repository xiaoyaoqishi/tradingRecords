# Trade Source Metadata Normalization (Additive Design Note)

## Why this note

Current source/broker semantics are mostly inferred from `Trade.notes`. This is brittle for long-term domain split, but must remain backward compatible while paste import behavior is protected.

This note defines a safe additive path without changing `/api/trades/import-paste` behavior.

## Current inference points (audit)

Backend:
- `backend/main.py` `list_trade_sources()`:
  - reads broker names from `trade_brokers`
  - parses `Trade.notes` using `来源券商:` pattern
- `list_trades` / `count_trades` / `get_statistics` / `list_trade_positions`:
  - `source_keyword` still filters by `Trade.notes.contains(...)`
- paste import:
  - writes `来源券商: ...` and `来源: 日结单粘贴导入` into `notes`

Frontend:
- `frontend/src/pages/TradeList.jsx` `parseSourceFromNotes()` parses display source from `notes`
- source filter values are fetched from `/api/trades/sources`

## Additive target (this step)

Introduce explicit metadata entity:
- `TradeSourceMetadata` (1:1 with `Trade`)
- fields:
  - `broker_name`
  - `source_label`
  - `import_channel`
  - `source_note_snapshot`
  - `parser_version`
  - `derived_from_notes`

Compatibility policy:
- keep legacy `notes` format untouched
- keep existing `source_keyword` filtering behavior untouched
- keep current paste import behavior untouched

## Minimal groundwork added in this step

- New model/table: `trade_source_metadata`
- New additive endpoints:
  - `GET /api/trades/{trade_id}/source-metadata`
    - returns stored metadata if present
    - otherwise returns legacy notes-derived fallback (non-persistent)
  - `PUT /api/trades/{trade_id}/source-metadata`
    - upserts explicit source metadata
- `/api/trades/sources` now also includes explicit metadata values when available
  while preserving legacy notes/broker-derived behavior

## Deferred (intentionally not done now)

- no paste import pipeline split
- no automatic metadata write during paste import
- no analytics migration to source metadata
- no frontend redesign around source metadata fields

## Next safe migration step (later)

1. Write metadata in parallel during paste import (dual-write).
2. Add characterization tests proving notes-compatible behavior remains stable.
3. Gradually migrate filtering from notes-only to metadata+notes fallback.
4. Only after parity is proven, consider de-emphasizing notes parsing.
