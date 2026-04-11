# Trading OS Canonical Model (ReviewSession + TradePlan)

## Canonical objects
- `Trade`: execution/ledger object.
- `TradeReview`: single-trade structured review only.
- `ReviewSession`: grouped/periodic/thematic/campaign review only.
- `TradePlan`: pre-trade planning object.

## Hard boundaries
- Grouped review canonical storage is only:
  - `review_sessions`
  - `review_session_trade_links`
- `/api/reviews*` is compatibility alias over ReviewSession API/service.
- No long-term dual-write or dual-storage for grouped review.
- Grouped review must not bulk-copy/mass-edit `TradeReview`.

## Selection and materialization rules
- `ReviewSession` creation supports selection modes:
  - `manual`
  - `filter_snapshot`
  - `plan_linked`
- `selection_target`:
  - `full_filtered` (default)
  - `current_page`
- At creation time, trade membership is materialized into explicit `review_session_trade_links`.
- `filter_snapshot_json` is reproducibility/audit metadata only, not dynamic membership.
- Membership is stable after creation unless user explicitly edits links.

## TradePlan status transition model
- Allowed transitions:
  - `draft -> active`
  - `active -> triggered | cancelled | expired`
  - `triggered -> executed | cancelled`
  - `executed -> reviewed`
- Terminal by default:
  - `cancelled`
  - `expired`
  - `reviewed`
- Linking trades to a plan does not auto-change status.

## Main workflow integration
- Trading workspace supports:
  - create ReviewSession from multi-selected trades
  - create ReviewSession from current filtered result set
  - create TradePlan from selected trades
- Plan workspace supports:
  - manage plan detail and linked trades
  - create plan-followup ReviewSession
- Review workspace displays linked trades as content cards (not ID-first).

## Saved Cohort scope
- Saved Cohort v1 remains optional/cuttable in this sprint.
- If added later, keep minimal fields only:
  - `name`
  - `description`
  - `selection_basis`
  - optional `filter_snapshot`
  - optional explicit trade links
