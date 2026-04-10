# Trading Record Refactor Plan (Incremental, Paste-Protected)

## Planning Principles

- Domain-first refactor, UI second.
- No big-bang rewrite.
- Paste import behavior is protected.
- Backward compatibility first; migration and rollback must be explicit.
- Each step must be independently verifiable.
- Per-trade structured review must use a distinct concept/entity (e.g., `TradeReview` or `TradeAnalysis`), not the existing periodic `Review` table.
- Existing periodic day/week/month `Review` stays separate unless a later explicit migration plan is approved.

## Phase 1 (Current): Audit

Completed in `docs/trading-system-audit.md` and `docs/trading-protected-behaviors.md`.

## Phase 2: Safety Rails Before Refactor

## Step 2.1 Add characterization tests for paste import

What to change:
- Introduce backend API characterization tests focused on `POST /api/trades/import-paste` and coupled read endpoints.

Why safer:
- Locks current behavior before domain changes.

How to verify:
- Run test suite and confirm baseline pass.
- Ensure tests assert current semantics, not idealized semantics.

## Step 2.2 Add coverage for source/broker coupling

What to change:
- Test `source_keyword` filters and `/api/trades/sources` behavior against imported records and custom broker values.

Why safer:
- Prevents hidden regressions from source-field refactor.

How to verify:
- Assertions on list/count/positions/statistics/sources consistency.

## Step 2.3 Enforce minimum automated coverage gate (required before domain changes)

Required coverage:
1. successful import with header
2. malformed mixed batch (partial success)
3. custom broker/source behavior
4. close matching against historical opens
5. same-batch close-before-open behavior
6. partial close split behavior
7. list/count baseline consistency
8. statistics/positions baseline consistency
9. detail edit compatibility for `error_tags`

Why safer:
- This blocks hidden behavior drift before schema/domain split starts.

How to verify:
- Gate CI/local run on this characterization suite before Phase 3 work.

## Phase 3: Domain Refactor (Small Safe Steps)

## Step 3.1 Introduce explicit domain enums/constants (non-breaking)

What to change:
- Add optional domain enums/constants in backend (and mirrored frontend options) for:
  - `opportunity_structure`
  - `edge_source`
  - `failure_type`
  - `review_conclusion`

Why safer:
- Adds explicit semantics without changing existing persistence immediately.

How to verify:
- Existing create/update flows still accept current payloads.
- New fields optional and ignored when absent.

Taxonomy compatibility note:
- Current phase keeps enum-backed validation as the default contract for consistency and queryability.
- Future extension path (deferred): allow `enum + custom text` by keeping enum fields as primary and adding explicit companion fields such as `*_custom_text` when `other`/unclassified cases are needed.
- Do not replace enum fields with free-text in this phase.

## Step 3.2 Add explicit structured review storage (additive)

What to change:
- Add a dedicated per-trade structured review entity (recommended name: `TradeReview` or `TradeAnalysis`, linked to `trade_id`, 1:1).
- Do not reuse the periodic `Review` concept/table for per-trade structured review semantics.
- Candidate fields:
  - `entry_thesis`
  - `opportunity_structure`
  - `edge_source`
  - `invalidation_valid_evidence`
  - `invalidation_trigger_evidence`
  - `invalidation_boundary`
  - `management_actions`
  - `exit_reason`
  - `failure_type`
  - `review_conclusion`
  - `review_tags`
  - `research_notes`

Why safer:
- Separates structured review semantics from raw execution ledger while keeping legacy `trades` stable.
- Avoids semantic coupling/confusion with cadence-based periodic reviews.

How to verify:
- New migration applies cleanly to existing DB.
- Legacy reads/writes continue unchanged.

## Step 3.3 Add explicit import-source metadata (additive)

What to change:
- Add first-class source metadata fields/entity for imported rows (e.g., source type, broker name, import batch id, raw row snapshot).
- Keep existing `notes` format for compatibility during transition.

Why safer:
- Decouples source logic from brittle note parsing without breaking existing filters immediately.

How to verify:
- Import still writes legacy notes markers.
- New metadata is populated in parallel.

## Step 3.4 Refactor paste pipeline into two internal layers

What to change:
- Internally separate:
  1. parse/raw import layer
  2. normalization/enrichment/matching layer
- Preserve endpoint contract and output.

Why safer:
- Improves maintainability while preserving user-facing behavior.

How to verify:
- Characterization tests from Phase 2 all green.

## Step 3.5 Compatibility read model and gradual write migration

What to change:
- API response can continue to expose legacy fields while adding new structured fields.
- Trade form/detail uses new structured fields where possible, with fallback to legacy text.

Why safer:
- Prevents breaking existing clients and existing records.

How to verify:
- Old records still editable/viewable.
- New records persist both structured data and necessary compatibility projections.

## Step 3.6 Backfill and migration notes

What to change:
- Add one-time backfill script/endpoint for mapping legacy fields into new structures where deterministic.
- Document non-deterministic mappings as manual review required.

Why safer:
- Keeps historical data usable under new model.

How to verify:
- Before/after record counts, null-rate checks, spot checks for mapped fields.

## Phase 4: Minimal API/UI Adjustments

## Step 4.1 Minimal form/list/detail updates

What to change:
- Add minimal editable/viewable fields for structured review dimensions.
- Keep paste import modal UX unchanged.

Why safer:
- Domain correctness improves without broad UI redesign risk.

How to verify:
- Manual smoke test of create/edit/import/list/detail paths.

## Step 4.2 Preserve old behavior contracts

What to change:
- Keep existing endpoints and payload compatibility where possible.
- Only additive API changes unless migration complete.

Why safer:
- Reduces integration breakage.

How to verify:
- Existing frontend routes continue to function.

## Phase 5: Analytics and Review Evolution

## Step 5.1 Derived metrics from explicit fields

What to change:
- Add reproducible metrics and filters by `opportunity_structure`, `edge_source`, `failure_type`, `review_conclusion`.

Why safer:
- Enables trustworthy analytics after domain model is explicit.

How to verify:
- Deterministic query outputs and regression tests.

## Step 5.2 Research workflow support

What to change:
- Add query surfaces for pattern-research logs and tag-based research slices.

Why safer:
- Builds on stable domain semantics, not free-text heuristics.

How to verify:
- Use-case validation: retrieve past trades by pattern/failure class and compare review conclusions.

## Migration And Rollback Strategy (For Schema Changes)

For each migration:
- Forward:
  - add tables/columns as nullable/additive first
  - deploy code with dual-read compatibility
- Backfill:
  - idempotent script with logging and dry-run mode
- Rollback:
  - keep old fields untouched until cutover complete
  - feature flags or compatibility switches for API reads

Do not drop legacy fields in early phases.

## Preferred Execution Order

1. Phase 2 Step 2.1 and 2.2: characterization suite + source/broker coupling checks
2. Phase 2 Step 2.3: enforce required automated coverage gate
3. Phase 3 Step 3.1: add explicit enums/constants (non-breaking)
4. Phase 3 Step 3.2: introduce distinct per-trade `TradeReview`/`TradeAnalysis` structure (not periodic `Review`)
5. Phase 3 Step 3.3 and 3.4: import-source metadata + internal parse/normalize split
6. Phase 3 Step 3.5 and 3.6: compatibility reads/writes + backfill/migration notes
7. Phase 4: minimal API/UI exposure updates without paste UX redesign
8. Phase 5: analytics evolution after domain semantics are explicit and verified
