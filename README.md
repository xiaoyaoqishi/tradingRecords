[中文文档](./README.zh-CN.md)

# tradingRecords: Self-Hosted Personal Workspace

## Positioning
`tradingRecords` is a self-hosted personal multi-app workspace. It combines trading records and review, notes, server monitoring, personal ledger, unified login, and a shared portal in one repository.

## Module Map
- `Trading`: Trade records, analytics, review sessions, plans, and research or knowledge workflow.
- `Notes`: Notebooks, diary and document notes, backlinks, todo, and recycle flow.
- `Monitor`: Admin-side server metrics, site checks, users, and audit logs.
- `Ledger`: Standalone personal finance app centered on import batches, review workbench, rules, merchants, and analytics.
- `Portal`: Static home page and login entry for the workspace.
- `Backend`: Shared FastAPI API, auth, data permissions, uploads, and SQLite-backed services.

## Current Capabilities
### Trading
- Trade CRUD, filters, search options, and position views.
- Statistics and analytics endpoints for trading records.
- Paste-based trade import with staged parsing and matching.
- Structured per-trade review data and review taxonomy support.
- Review sessions with linked trades and selection-based generation.
- Trade plans with linked trades and follow-up review flow.
- Knowledge items with primary category + secondary category folders, tags, statuses, and note links.
- Knowledge maintain workspace supports long-content bottom scroll buffer and a back-to-top button for long pages.
- Review session and trade plan workspaces support long-content bottom scroll buffer and a back-to-top button for long pages.
- Review session and trade plan workspaces support collapsible sidebars, grouped sections (`研究内容` / `属性与关联`), and title-free main panels.
- Trading recycle bin for trades, brokers, review sessions, plans, and knowledge items.

### Notes / Knowledge
- Notebook management for diary and document collections.
- Diary and document note CRUD with shared editor flow.
- Search, calendar, diary tree, and "history today" style browsing.
- Wiki-link resolution and backlinks between notes.
- Todo management in the notes workspace.
- Notes recycle bin with restore and purge flow.

### Monitor / Admin
- Login, logout, setup, and session check flow through the shared backend.
- Admin-only monitor APIs for server metrics and site checks.
- Realtime and historical server metrics.
- Site target CRUD and per-target result history.
- User management with role and password operations.
- Per-user module visibility for `trading`, `notes`, and `ledger`.
- Per-module data permissions with `read_write` and `read_only` modes.
- Audit log collection, listing, filtering, and deletion.

### Ledger
- Import-first bookkeeping pipeline centered on `import batches`.
- Source detection and row-level staging (`ledger_import_rows`) before final commit.
- Layered rule engine (source -> merchant normalization -> category -> fallback), with built-in CN rules and per-layer trace.
- The `/dedupe` step is retained as a review-stage cleanup action, but automatic duplicate tagging is currently disabled to avoid false positives on frequent same-merchant spending.
- Review queue backend closure: bulk category fix, bulk merchant normalization, bulk confirm, and one-click rule generation from manual fixes.
- Import review workbench supports creating rules directly from selected samples (merchant/category/both/source-platform, no category-id input, category dropdown includes "其他", hit-range preview, duplicate skipping, and selectable re-identify scope: unconfirmed or all rows).
- Review workbench hardening: batch selection, replay rules for the current batch, reclassify pending rows, and a table-top action toolbar for refresh/replay/commit.
- Review workbench supports configurable high-confidence threshold and one-click confirm for high-confidence pending rows.
- Rule generation hardening: hit-range preview and estimated impact, duplicate-rule skipping, and scope choice between profile-bound and global.
- Commit only imports `confirmed` rows and keeps batch/row/transaction linkage.
- Imported datetime is normalized to date-only precision (`YYYY-MM-DD`, no time part).
- Merchant dictionary (`ledger_merchants`) supports editing canonical name/aliases/default categories and displays recent linked samples.
- Unified tabular parser supports `csv/xls/xlsx` (including HTML-table style `.xls` exports).
- Phase 3 MVP frontend now includes:
  - Import Center (`/ledger/imports`) for batch lifecycle operations.
  - Import Review Workbench (`/ledger/imports/:batchId/review`) with explain visibility and batch actions.
  - Basic Analytics page (`/ledger/analytics`).
  - Merchant Dictionary page (`/ledger/merchants`).
  - Rules Management page (`/ledger/rules`) with create/edit/delete plus hit count and last hit timestamp.
- REST APIs:
  - `POST /api/ledger/import-batches`, `GET /api/ledger/import-batches`, `GET /api/ledger/import-batches/{id}`
  - `POST /api/ledger/import-batches/{id}/parse`, `/classify`, `/dedupe`, `/commit`
  - `GET /api/ledger/import-batches/{id}/review-rows`, `GET /api/ledger/import-batches/{id}/review-insights`
  - `POST /api/ledger/import-batches/{id}/review/bulk-category`, `/review/bulk-merchant`, `/review/bulk-confirm`, `/review/reclassify-pending`, `/review/generate-rule`
  - `GET /api/ledger/categories`
  - `GET/POST/PUT /api/ledger/merchants`
  - `GET/POST/PUT/DELETE /api/ledger/rules`
  - `GET /api/ledger/analytics/summary`, `/analytics/category-breakdown`, `/analytics/platform-breakdown`, `/analytics/top-merchants`, `/analytics/monthly-trend`, `/analytics/unrecognized-breakdown`
  - Frontend now uses import-centered workflow as primary entry; Phase 4 (AI/report enhancement) is not started.
  - User-facing source/platform/category/status values are rendered in Chinese labels in the review workbench.

## Quick Start
### Prerequisites
- Python 3
- Node.js
- npm
- Optional: `tmux`
- For production deployment: Linux, `nginx`, and `systemd`

### Install Dependencies
```bash
cd backend
pip install -r requirements.txt

cd ../frontend
npm install

cd ../frontend-notes
npm install

cd ../frontend-monitor
npm install

cd ../frontend-ledger
npm install
```

### Fastest Local Start
```bash
./dev.sh up
```

Open the portal at `http://127.0.0.1:5172`.

`dev.sh` automatically discovers `frontend*` directories that contain a `package.json` with a `dev` script, then starts them together with the FastAPI backend and the local portal gateway.

## Routes & Entry Points
- `/`: Portal home page for the workspace.
- `/login`: Shared login page.
- `/trading/`: Trading SPA entry; the app redirects to `/trading/dashboard`.
- `/notes/`: Notes workspace entry.
- `/monitor/`: Monitor and admin workspace entry.
- `/ledger/`: Ledger SPA entry; the app redirects to `/ledger/imports`.
- `/api/*`: Shared FastAPI API for auth, trading, notes, monitor, ledger, uploads, and related services.

## Architecture Overview
The portal is the entry layer for the workspace. Each frontend is built independently and served on its own subpath, while FastAPI provides the shared API surface behind `/api/*`. Persistent data is stored in SQLite under `backend/data`. In production, Nginx handles path dispatch for the portal, each SPA, and the API, including SPA fallbacks; `/ledger` is redirected to `/ledger/`.

## Directory Structure
- `backend/`: Shared FastAPI backend, including the trading domain and the standalone ledger backend domain under `/api/ledger/*`.
  - `core/`: App config, database setup, middleware, request context, and security helpers.
  - `routers/`: API route registration for auth, trading, notes, monitor, ledger, uploads, and more.
  - `services/`: Shared service modules plus ledger-specific services.
  - `models/`: SQLAlchemy models for workspace domains.
  - `schemas/`: Pydantic schemas for API input and output.
  - `trading/`: Trading-specific business logic such as imports, analytics, reviews, plans, and knowledge.
  - `data/`: SQLite database, uploads, and runtime data.
- `frontend/`: Trading frontend served under `/trading/`.
- `frontend-notes/`: Notes frontend served under `/notes/`.
- `frontend-monitor/`: Monitor and admin frontend served under `/monitor/`.
- `frontend-ledger/`: Independent ledger frontend served under `/ledger/`.
- `portal/`: Static portal and login entry used in local development and production.
- `deploy/`: Deployment scripts, Nginx config, and the systemd service unit.
- `dev.sh`: Unified local development script for backend, portal, and auto-discovered frontends.

## Tech Stack
- FastAPI / SQLAlchemy / Pydantic / Uvicorn
- SQLite
- React / Vite / Axios / Ant Design
- Recharts
- Nginx / systemd / shell scripts

## Environment Variables
| Variable | Purpose |
| --- | --- |
| `DEV_MODE` | Enables local development behavior for the backend. |
| `COOKIE_SECURE` | Controls whether auth cookies require HTTPS. |
| `PORTAL_DEV_PORT` | Local port for the portal dev gateway. |
| `PORTAL_BACKEND_PORT` | Backend port used by the local portal proxy. |
| `PORTAL_TRADING_PORT` | Trading frontend dev port used by the local portal proxy. |
| `PORTAL_NOTES_PORT` | Notes frontend dev port used by the local portal proxy. |
| `PORTAL_MONITOR_PORT` | Monitor frontend dev port used by the local portal proxy. |
| `PORTAL_LEDGER_PORT` | Ledger frontend dev port used by the local portal proxy. |
| `POEM_CACHE_TTL` | Optional cache TTL for the daily poem endpoint. |
| `POEM_REMOTE_URL` | Optional remote source for the daily poem endpoint. |
| `JINRISHICI_TOKEN` | Optional token for the configured daily poem source. |

## Common Commands
```bash
./dev.sh up
./dev.sh down
./dev.sh status
./dev.sh attach
pytest -q backend/tests

cd frontend && npm run build
cd frontend-notes && npm run build
cd frontend-monitor && npm run build
cd frontend-ledger && npm run build
```

## Deployment
Use `deploy/setup.sh` for first-time Linux host setup and `deploy/update.sh` for routine updates on an existing server. Production routing lives in `deploy/nginx.conf`, and the backend service is managed by `deploy/trading.service`. The deployed path layout includes `/ledger/`, and SPA fallback handling is already configured for the frontend apps.

## Docs & Validation
- [docs/ledger-smoke-checklist.md](./docs/ledger-smoke-checklist.md)
- [scripts/ledger-smoke.sh](./scripts/ledger-smoke.sh)
- [README.zh-CN.md](./README.zh-CN.md)
