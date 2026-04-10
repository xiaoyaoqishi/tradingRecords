# Trading Protected Behaviors (Characterization Checklist)

This file defines behaviors that must remain stable while refactoring the trading-record subsystem, especially paste import.

## A. Paste Import Workflow (Hard Protection)

## PB-01 Successful import with header row

Given:
- tab-delimited text with the 10-column broker statement header

Expect:
- header skipped
- valid rows imported
- response includes correct `inserted/skipped/errors`

## PB-02 Successful import without header row

Given:
- tab-delimited rows only

Expect:
- first row treated as data
- imports match current behavior

## PB-03 Malformed row handling is non-fatal to batch

Given:
- mixed valid/invalid rows (bad date, bad direction, quantity <= 0, too few columns)

Expect:
- invalid rows reported in `errors`
- valid rows still imported
- transaction still commits successful subset

## PB-04 Open-row deduplication behavior preserved

Given:
- repeated open rows with same dedup key fields

Expect:
- duplicates counted as `skipped`
- no duplicate open rows inserted for that key

## PB-05 Close-row is not deduplicated like open-row

Given:
- close rows representing offset logic

Expect:
- close rows attempt reconciliation each time
- not skipped by open-row dedup rule

## PB-06 Close matching can consume historical open positions

Given:
- existing open rows in DB + pasted close rows

Expect:
- close rows must match broker-scoped historical opens in FIFO-like order (`open_time`, `id`)
- when matched exactly, matched open row transitions to `status=closed` rather than creating an extra open row
- matched row `commission/pnl/close_time/close_price` update behavior remains baseline-compatible
- if historical opens are insufficient, close row is reported in `errors` and successful rows still commit

## PB-07 Close matching can consume same-batch opens regardless of row order

Given:
- in pasted text, close appears before corresponding open

Expect:
- pre-validation still allows close to consume same-batch opens even when close text line appears first
- DB apply order remains: insert opens first, then apply closes
- successful batch must not require users to manually reorder pasted lines

## PB-08 Partial close split behavior preserved

Given:
- close quantity smaller than matched open quantity

Expect:
- open row quantity reduced
- closed split row created
- commission/pnl prorated as currently implemented
- open residual row keeps `status=open` and remains queryable by `/api/trades/positions`
- closed split row remains queryable by `/api/trades/statistics`

## PB-09 Broker-scoped matching preserved

Given:
- import with `broker` set

Expect:
- dedup/historical close matching scoped by `来源券商: broker`
- different broker scope does not cross-match

## PB-10 Source markers in notes remain available during transition

Given:
- paste import with/without broker

Expect:
- legacy source note patterns remain readable by current list/filter UI

## B. Coupled Read Behavior

## PB-11 Trade list and count stay consistent

Expect:
- `/api/trades` and `/api/trades/count` align under same filters

## PB-12 Source filter behavior preserved

Expect:
- `source_keyword` filtering still works for list/statistics/positions endpoints

## PB-13 Source options endpoint behavior preserved

Expect:
- `/api/trades/sources` still returns broker list and discovered historical source brokers

## PB-14 Detail edit compatibility preserved

Expect:
- `error_tags` round-trip behavior remains (JSON string storage + UI parse/stringify)

## PB-15 Derived analytics baseline is preserved before explicit analytics migration

Expect:
- until analytics definitions are explicitly migrated, `/api/trades/statistics` output semantics stay baseline-compatible
- until analytics definitions are explicitly migrated, `/api/trades/positions` output semantics stay baseline-compatible
- for the same dataset and filters, refactor branches must match baseline values for:
  - statistics totals/win-loss/pnl aggregates
  - open-position net quantity/avg cost/open_since/last_trade_date semantics

## C. Minimum Characterization Test Set For Phase 2

Recommended minimum automated coverage:

1. Import success with header (`PB-01`)
2. Import malformed mixed batch (`PB-03`)
3. Key imported fields preserved (`trade_date/contract/direction/qty/status/commission/pnl/notes`)
4. Custom broker behavior (`PB-09`, `PB-13`)
5. Close matching against historical opens (`PB-06`)
6. Same-batch close-before-open behavior (`PB-07`)
7. Partial close split behavior (`PB-08`)
8. Trade list/count consistency (`PB-11`)
9. Statistics/positions baseline consistency (`PB-12`, `PB-15`)
10. Detail edit compatibility (`PB-14`)

## D. Suggested Lightweight Test Approach

Preferred:
- Backend characterization tests using `pytest` + FastAPI `TestClient`
- Temporary SQLite DB fixture per test session
- `DEV_MODE=1` in tests to bypass auth middleware

If introducing pytest infra is temporarily too heavy:
- add a deterministic script-based check runner (curl/http client + sqlite assertions)
- tradeoff: weaker failure reporting and less maintainable than pytest

## E. Regression Gate Rule

Before each meaningful domain-model change:
- run all protected-behavior checks
- if any fail, either:
  - restore compatibility behavior, or
  - add explicit migration/compat layer and document accepted behavior shift before merging
