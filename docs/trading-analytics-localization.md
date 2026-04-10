# Trading Analytics + Localization Notes

## Canonical Value Policy

- Backend canonical taxonomy values remain English keys:
  - `opportunity_structure`
  - `edge_source`
  - `failure_type`
  - `review_conclusion`
- API write/read payload values for structured review continue using canonical English keys.
- Frontend displays Chinese labels through centralized mapping only.

Mapping module:
- `frontend/src/features/trading/localization.js`
  - `TAXONOMY_ZH`
  - `getTaxonomyLabel(field, canonicalValue)`
  - `taxonomyOptionsWithZh(field, values)`

## New Analytics Endpoint

- Added additive endpoint: `GET /api/trades/analytics`
- Existing endpoints and semantics are unchanged:
  - `/api/trades/import-paste`
  - `/api/trades/statistics`
  - `/api/trades/positions`

### Analytics dimensions returned

1. `overview`
- total/open/closed trades
- win/loss count
- win rate
- total pnl
- avg pnl per closed trade
- avg win/avg loss
- profit factor
- open position count

2. `time_series`
- `daily` / `weekly` / `monthly`
- trade_count / win_count / loss_count / win_rate / total_pnl

3. `dimensions`
- `by_symbol`
- `by_source` (metadata-first, notes fallback)
- `by_review_field` (taxonomy slices)

4. `behavior`
- error tag frequencies
- planned vs unplanned
- strategy_type / market_condition / timeframe distributions
- overnight split

5. `positions`
- open positions summary rows

6. `coverage`
- TradeReview coverage
- TradeSourceMetadata coverage
- legacy-source-only count
- source-missing count

## Dashboard Data Sources

- Main analytics page now reads `tradeApi.analytics(...)`.
- Source filter options still come from `/api/trades/sources`.
- Structured review dimensions use canonical keys from backend and render Chinese labels in UI.

## Compatibility Notes

- Paste import workflow and matching logic remain unchanged.
- Broker-scoped matching, same-batch close-before-open, partial close split semantics remain unchanged.
- Legacy `notes` and `review_note` remain available as secondary compatibility fields in workspace forms/panels.
