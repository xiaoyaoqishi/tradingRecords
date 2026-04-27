# Ledger Smoke Checklist

## Preconditions
- Backend dependencies are installed.
- Frontend dependencies are installed.
- Build verification:
  - `cd frontend-ledger && npm run build`
- API regression check:
  - `cd backend && python3 -m pytest -q tests/test_ledger_import_pipeline.py`

## Frontend Smoke (Phase 3 MVP)
1. Open `/ledger/`, should redirect to `/ledger/imports`.
2. In Import Center (`/ledger/imports`):
   - Upload `csv/xls/xlsx` file and create a new batch.
   - Run `parse -> classify -> 清理重复标记` from row actions.
   - Note: duplicate tagging is currently disabled by default, so this step only clears old duplicate flags and duplicate count may stay `0`.
   - Confirm batch list columns are visible: file/source/status/total/pending/duplicate/confirmed.
3. Click "进入校对台" and open `/ledger/imports/{id}/review`:
   - Table shows: date/amount/raw text/source/platform/merchant/category/confidence.
   - Source/platform/category/status display labels should be Chinese (no raw enum values like `wechat` / `wechat_pay` / `alipay` in table columns).
   - Header dropdown filters for summary/source/platform/merchant/category are available, sorted by frequency and showing counts.
4. In review workbench:
   - Filter pending and unrecognized by status tabs.
   - Use table header filters and verify fuzzy search in dropdown options.
   - Adjust high-confidence threshold and click `一键确认高阈值`, verify pending rows are batch-confirmed.
   - Select one or more unresolved rows, click `从勾选记录生成规则`.
   - Verify modal has no `目标分类编号` input; use `目标分类` Chinese dropdown.
   - Click `预览命中范围`, verify estimated hit count and sample list.
   - Select re-identify scope (`重识别未确认` or `重识别全部记录`), then click confirm and verify table refresh.
   - Category dropdown should include `其他`; rule type should include `来源/平台规则`.
   - Verify commit button is enabled only when `confirmed > 0`, then commit.
5. Open Merchant Dictionary (`/ledger/merchants`):
   - Verify canonical name / aliases / default category / hit count are rendered.
6. Open Rules Management (`/ledger/rules`):
   - Verify list includes existing rules.
   - Create one rule, edit it, then delete it.
   - Verify the deleted rule no longer appears in the list.

## API Smoke (Phase 2 Features)
1. `POST /api/ledger/import-batches/{id}/review/bulk-category`
2. `POST /api/ledger/import-batches/{id}/review/bulk-merchant`
3. `POST /api/ledger/import-batches/{id}/review/bulk-confirm`
4. `POST /api/ledger/import-batches/{id}/review/generate-rule`
5. `POST /api/ledger/import-batches/{id}/commit`
6. `GET /api/ledger/categories`

## Pass Criteria
- Import Center / Review Workbench / Merchant Dictionary routes are reachable.
- Import review table is usable as the primary workflow.
- Explain and duplicate evidence are visible and traceable.
- At least one bulk review action succeeds.
- Rule generation from selected rows is directly usable without category-id input.
- Commit button state matches confirmed-row count.

## Current Scope / Not In This Phase
- This phase does not include AI fallback enhancement.
- This phase does not include analytics/report pages refactor.
- Ledger keeps only the import-batch canonical flow; legacy accounts / transactions / recurring pages are removed.
