# Trading Record Subsystem Audit (Phase 1)

## Scope And Method

This audit only covers the trading-record subsystem and its directly coupled flows:

- trade recording and paste import
- trade source/broker metadata used by import/filtering
- per-trade and periodic review data exposed in the trading app
- derived statistics/positions based on trade records

No refactor was done in this phase; this is read-only analysis.

## 1. Subsystem Boundary (What Is In / Out)

### In-scope files (core)

Backend:
- `backend/models.py` (`Trade`, `Review`, `TradeBroker`)
- `backend/schemas.py` (trade/review/broker request-response schemas)
- `backend/main.py` trade/review/broker endpoints and paste import pipeline

Frontend:
- `frontend/src/api/index.js` (`tradeApi`, `reviewApi`, `brokerApi`)
- `frontend/src/pages/TradeList.jsx` (list, paste import modal, position view, source parsing)
- `frontend/src/pages/TradeForm.jsx` (manual create/edit trade and per-trade review fields)
- `frontend/src/pages/Dashboard.jsx` (trade-derived analytics + positions)
- `frontend/src/pages/ReviewList.jsx` (daily/weekly/monthly review CRUD)
- `frontend/src/pages/BrokerManage.jsx` (broker metadata CRUD)
- `frontend/src/utils/futures.js` (symbol normalization/labels in UI)

Docs coupled to this subsystem:
- `README.md` trading APIs and behavior description

### Adjacent but out-of-scope (unless blocking)

- notes/news/monitor modules
- auth, upload, notebook/note/todo/news endpoints
- deployment scripts not specific to trading-record behavior

## 2. Where Paste Import Lives

### Frontend entry

- Paste UI and broker input: `frontend/src/pages/TradeList.jsx`
- API call: `tradeApi.importPaste({ raw_text, broker })`

### Backend parsing and normalization

- Endpoint: `POST /api/trades/import-paste` in `backend/main.py`
- Parsing helpers:
  - `_parse_cn_date`
  - `_parse_float`
  - `_map_direction`
  - `_map_open_close`
  - `_parse_paste_row`
- Open/close reconciliation helpers:
  - `_apply_close_fill_to_db`
  - `_copy_trade_for_closed_part`
  - `_position_side`, `_state_key_contract`

### Storage flow

Current flow is:
1. Parse raw pasted lines (`\t`-split, optional header skip).
2. Convert each valid row directly into a `Trade` ORM object.
3. Deduplicate only open rows against existing DB rows.
4. Validate close rows against history open pool + current batch open pool.
5. Insert open rows first.
6. Apply close rows by matching open positions and mutating/splitting rows.
7. Commit once, return `{ inserted, skipped, errors }`.

## 3. Current Data Model

## 3.1 Trade model (`trades`)

`Trade` currently mixes three concerns in one table:

- execution ledger fields (date/symbol/direction/prices/qty/status/fees/pnl)
- discretionary review/decision fields (entry logic, strategy type, market condition, etc.)
- behavior/discipline + free-text reflection fields (error tags, review note, notes)

There is no explicit layered entity boundary between raw import data, normalized review data, and derived analytics.

## 3.2 Review model (`reviews`)

`Review` stores day/week/month periodic review records in one table with many optional text fields by review type. It is not linked to individual trades.

## 3.3 Broker model (`trade_brokers`)

`TradeBroker` stores broker metadata; import filtering still depends on text embedded in `Trade.notes`.

## 4. Raw Imported vs Review vs Derived (Current State)

## 4.1 Raw imported execution data (currently implicit)

Paste import writes directly to `trades` fields:
- `trade_date`, `instrument_type="期货"`, `symbol` (normalized from contract), `contract`, `category`
- `direction`, `open_time` (fixed 09:00), `close_time` (closed rows fixed 15:00)
- `open_price`, `close_price` (closed rows set equal to成交价), `quantity`
- `commission`, `pnl`, `status`
- `notes` (source markers such as `来源券商:` and `来源: 日结单粘贴导入`)

No dedicated raw-import table keeps the original row payload, parser version, or normalization metadata.

## 4.2 Structured review data (currently partial and mixed)

In `Trade`, review-like fields exist but are mixed and mostly text:
- `entry_logic`, `exit_logic`, `strategy_type`, `market_condition`, `timeframe`, `core_signal`
- `pre_opportunity`, `pre_win_reason`, `pre_risk`
- `post_quality`, `post_root_cause`, `post_replicable`, `review_note`
- `error_tags` (JSON string in practice, no backend validation)

In `Review`, periodic review is structured by cadence but still text-heavy and not tied to specific trade records.

## 4.3 Derived analytics

Derived endpoints read from `trades` (mainly `status='closed'`):
- `/api/trades/statistics`: pnl aggregates, streaks, symbol/strategy pnl, error tag counts
- `/api/trades/positions`: net open position state built from `status='open'`

Derived logic is embedded in endpoint code, not represented as separate persisted analytics entities.

## 5. Domain-Intent Gap Analysis

Required target concepts vs current state:

- raw trade record: partially present in `trades`; raw source row is not preserved.
- imported trade source: stored as note text, not first-class field/entity on trade records.
- instrument/symbol + direction: explicit and usable.
- entry thesis: partially present (`entry_logic`, `pre_*` text).
- opportunity structure/pattern: implicit in `strategy_type`/`pre_opportunity`; no explicit taxonomy.
- edge source: implicit/free text only.
- invalidation logic: mostly buried in `pre_risk` free text.
- management actions: partly in behavior flags and `during_plan_changed` text.
- exit reason: implicit in `exit_logic` text.
- failure type: not explicit enum; only coarse `error_tags` strings.
- review conclusion: partly represented by `post_quality`, but not explicit verdict dimensions.
- tags/labels: only `error_tags` (JSON text) and generic `notes`.
- research log/pattern research notes: no dedicated structure.

Summary: the schema has many fields, but core review semantics are still mostly implicit and text-bound.

## 6. Behavior That Must Be Protected (Regression-Critical)

High-risk behavior to preserve:

- Paste import UX and payload contract (`raw_text`, optional `broker`).
- Header row optionality and 10-column tab paste workflow.
- Open-row deduplication semantics and skip counting.
- Close-row reconciliation semantics (history + same-batch opens, open-first then close apply).
- Partial close split behavior and auto-generated source notes.
- Broker-scoped matching behavior during import and filtering.
- Existing source filtering/list behavior based on `notes` markers.
- Current trade list/detail/dashboard behavior consuming import results.

Detailed protected checklist is in `docs/trading-protected-behaviors.md`.

## 7. Fragility / Technical Debt Identified

- No automated tests at all for trading subsystem.
- Import pipeline tightly couples parse/normalize/store/matching in one endpoint.
- Source attribution relies on parsing free text in `notes`.
- Open-row dedup uses exact float equality and a narrow field set; can skip legitimate duplicates or miss near-equal duplicates.
- Schema migration strategy is ad-hoc (`create_all` + limited manual ALTERs) and currently does not cover future trade/review schema evolution robustly.
- Many review semantics exist as free text fields without enum/domain constraints.
- One helper (`_apply_fill_to_state`) appears unused, indicating incomplete or stale layering.

## 8. Minimum Safe Refactor Boundary

Recommended minimum boundary for this refactor:

- Backend trade/review/broker models + schemas + endpoints only
- Frontend trading app pages/API client directly consuming those fields
- README trading section updates as contract changes occur

Do not refactor notes/news/monitor internals unless required as a blocker.

## 9. Incremental Evolution Strategy (Recommended)

Use incremental schema evolution (not big-bang replacement):

1. Keep existing `trades` table behavior stable first.
2. Add explicit new structures for:
   - raw import metadata/raw rows
   - structured per-trade review semantics
3. Backfill from legacy text fields where possible.
4. Keep old fields readable during transition.
5. Migrate UI/API gradually, preserving paste import behavior.

Rationale:
- maximizes backward compatibility
- keeps existing workflows operational
- enables staged validation before field deprecation

## 10. Ambiguities To Resolve During Refactor

- Final taxonomy for `opportunity_structure` and `edge_source` (examples are given but not final).
- Whether periodic `reviews` should stay separate or partially map to per-trade review conclusions.
- Which legacy free-text fields remain canonical vs become deprecated after backfill.

Safe default: add new explicit fields as optional first, keep legacy fields untouched, and dual-read/dual-write until characterization tests pass.
