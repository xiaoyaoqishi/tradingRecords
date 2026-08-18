[中文文档](./README.zh-CN.md)

# tradingRecords: Self-Hosted Personal Workspace

## Positioning
`tradingRecords` is a self-hosted personal multi-app workspace. It combines trading records and review, notes, admin-side site checks, personal ledger, unified login, and a shared portal in one repository.

## Module Map
- `Trading`: Trade records, analytics, structured per-trade reviews, plans, and research workflow.
- `Notes`: Notebooks, diary and document notes, wiki-link navigation, todo, and recycle flow.
- `Monitor`: Admin-side site checks, users, and audit logs.
- `Ledger`: Standalone personal finance app centered on import batches, review workbench, rules, merchants, analytics, and an in-app asset library.
- `Portal`: Static home page and login entry for the workspace.
- `Backend`: Shared FastAPI API, auth, data permissions, uploads, and SQLite-backed services.

## Current Capabilities
### Trading
- Trade CRUD, filters, search options, position views, and opening/closing timestamps in the trade table.
- Crypto trade fees and P&L are entered in USDT. The form automatically loads an editable USD/CNY rate and stores the USDT source amount, applied rate, and converted CNY value; records show CNY with USDT in parentheses, while dashboards and analytics consistently aggregate CNY.
- New and edited trades select instruments from a searchable canonical catalog instead of free text. The Maintenance page provides instrument and broker tabs, with instrument create/edit/delete support; editing an instrument code also updates existing trades and plans.
- Trade-record favorite/rating controls and their favorite, rating, and custom-sort filters have been removed.
- Trade behavior-discipline fields, violation markers, and related analytics have been removed without retaining historical values.
- Trade size fields and displays have been removed from create/edit, tables, details, linked summaries, position views, and APIs without retaining historical values.
- The trade margin field has been removed from forms, APIs, and storage without retaining historical values.
- Supplemental trade information, futures-specific metadata, and pre/during/post trade fields have been removed from forms, analytics, APIs, and storage without retaining historical values.
- Trade forms no longer expose source information, supplemental records, or error tags, and their historical values are removed; trade decisions are limited to entry logic, exit logic, strategy type, and core signal.
- New-trade creation includes a dedicated `Trade Decision` tab, and trade details show the same decision content in a read-only section.
- New trades require current stop-loss, target points, and capital allocation percentage; later edits append timestamped snapshots of all three values so pyramiding changes remain traceable.
- Trade date is derived from the single user-facing open-time field, and risk-point history timestamps are displayed in China Standard Time.
- The trade records page uses single-record operations and no longer provides multi-select or filter-based bulk actions.
- Statistics and analytics endpoints for trading records, with dashboard filters for date, instrument type, and symbol.
- Trading opens on an action-oriented home workspace that summarizes current positions, monthly PnL, recent trades, active plans, review/source reminders, and recent research; the full dashboard remains dedicated to deep analytics.
- Trading frontend now includes four switchable themes (`ink` / `light` / `tech` / `dark`) through a sidebar dropdown selector, with `ink` preserved as the default paper-style theme and the selected theme persisted locally.
- Paste-based trade import implementation is retained, but its trade-records-page entry is temporarily offline.
- Structured per-trade review data and review taxonomy support.
- Trade details display structured reviews in read-only mode, include leverage for crypto trades, and list every research document that references the trade as a title link; review maintenance is available only from the trade edit page.
- Trade plans with linked trades.
- The former grouped review-session workbench and its plan follow-up flow have been removed; structured per-trade reviews remain available.
- Trading subpages use consistent compact action bars without standalone title-and-description headers; primary actions stay on the right, and the trade-record filters, view switch, and create action share one control row.
- A research document can search for and reference multiple trade records. Reader mode pins their date, direction, prices, P&L, and status above the body and opens trade details in an in-page drawer.
- Trading now includes an independent `Research` submodule with a document-style folder tree and single reading/editing area. Both research documents and folders support drag-and-drop moves and sibling ordering, while folders can also be dragged to change hierarchy; search, tags, pinning, wiki links/backlinks, and recycle flow are included. Images in the research reader support repeated proportional zooming, zooming out, reset, and drag-to-pan when enlarged. The rich-text editor can insert named collapsible blocks that accept images and other body content; all such blocks start collapsed in reader mode. Its rich-text toolbar matches the Notes document editor while its code, APIs, and tables remain trading-owned; legacy trading-scoped Notes data is copied into the research domain during runtime migration.
- Trading recycle bin for trades, brokers, and plans.

### Notes
- Notebook management for diary and document collections.
- Diary and document note CRUD with shared editor flow.
- Images in reading mode support repeated proportional zooming, zooming out, reset, and drag-to-pan when enlarged.
- Document files and folders can be dragged between folders or reordered among siblings; folder dragging can also change hierarchy, and the existing document move action remains available.
- Search, calendar, diary tree, and "history today" style browsing.
- Action-oriented Notes home with unified search, quick capture shortcuts, recent documents, actionable todos, and a compact writing rhythm overview.
- Wiki-link resolution and forward navigation between notes.
- Streamlined todo workspace with quick capture, optional scheduling and reminders, clear completion controls, filters, and an explicit bulk-management mode.
- Notes recycle bin with restore and purge flow.

### Monitor / Admin
- Login, logout, setup, and session check flow through the shared backend.
- Admin-only monitor APIs for site checks.
- Monitor frontend now includes four switchable themes (`light` / `ink` / `tech` / `dark`) through a sidebar dropdown selector, with theme choice persisted locally.
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
- Commit only imports `confirmed` / `approved` / `accepted` rows and keeps batch/row/transaction linkage.
- Imported datetime is normalized to date-only precision (`YYYY-MM-DD`, no time part).
- Merchant dictionary (`ledger_merchants`) supports editing canonical name/aliases/default categories and displays recent linked samples.
- Unified tabular parser supports `csv/xls/xlsx` (including HTML-table style `.xls` exports).
- Asset library (`/ledger/assets`) now supports long-term asset records, purchase cost, extra cost, usage and idle tracking, lifecycle events, sold review, and cash daily cost analysis within one tabbed page.
- Asset library lifecycle and analysis views now include a compact top-mounted event form, first-5 event collapse with show-all toggle, hover-only event delete action, richer lifecycle selector metrics, and expanded analysis charts for type mix, purchase-year trend, in-use efficiency, extra-cost ratio, ROI, and idle days.
- Ledger frontend now includes four switchable themes (`light` / `dark` / `ink` / `tech`) through a sidebar dropdown selector, with compact mode compatible across all themes.
- Current ledger pages include:
  - Import Center (`/ledger/imports`) for batch lifecycle operations.
  - Import Review Workbench (`/ledger/imports/:batchId/review`) with explain visibility and batch actions.
  - Basic Analytics page (`/ledger/analytics`).
  - Merchant Dictionary page (`/ledger/merchants`).
  - Rules Management page (`/ledger/rules`) with create/edit/delete plus hit count and last hit timestamp.
  - Asset Library page (`/ledger/assets`) with long-term records, purchase cost, extra cost, usage and idle tracking, lifecycle events, sold review, and cash daily cost analysis in a single tabbed workspace.
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
- Node.js 22.22.0 or newer
- npm
- Optional: `tmux`
- For production deployment: Linux, `systemd`, and Nginx

### Install Dependencies
```bash
cd backend
python3 -m pip install -r requirements.txt

cd ../frontend-trading
npm ci

cd ../frontend-notes
npm ci

cd ../frontend-monitor
npm ci

cd ../frontend-ledger
npm ci
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
- `/trading/`: Trading home workspace; records, analytics, plans, research, maintenance, and recycle remain available as dedicated subpages.
- `/notes/`: Notes workspace entry.
- `/monitor/`: Monitor and admin workspace entry.
- `/ledger/`: Ledger SPA entry; the app redirects to `/ledger/imports`.
- `/api/*`: Shared FastAPI API for auth, trading, notes, monitor, ledger, uploads, and related services.

## Architecture Overview
The portal is the entry layer for the workspace. Each frontend is built independently and served on its own subpath, while FastAPI provides the shared API surface behind `/api/*`. Persistent SQLite data is stored under `backend/data`; production uploads are stored outside the Git checkout through `UPLOAD_DIR`. In production, Nginx handles path dispatch for the portal, each SPA, and the API, including SPA fallbacks; `/ledger` is redirected to `/ledger/`.

## Directory Structure
- `backend/`: Shared FastAPI backend, including the trading domain and the standalone ledger backend domain under `/api/ledger/*`.
  - `core/`: App config, database setup, middleware, request context, and security helpers.
  - `routers/`: API route registration for auth, trading, notes, monitor, ledger, uploads, and more.
  - `services/`: Shared service modules plus ledger-specific services.
  - `models/`: SQLAlchemy models for workspace domains.
  - `schemas/`: Pydantic schemas for API input and output.
  - `trading/`: Trading-specific business logic such as imports, analytics, research, reviews, and plans.
  - `data/`: SQLite database and local runtime data. Production uploads are configured outside the repo.
- `frontend-trading/`: Trading frontend served under `/trading/`.
- `frontend-notes/`: Notes frontend served under `/notes/`.
- `frontend-monitor/`: Monitor and admin frontend served under `/monitor/`.
- `frontend-ledger/`: Independent ledger frontend served under `/ledger/`.
- `portal/`: Static portal and login entry used in local development and production.
- `deploy/`: Bare-metal deployment scripts, systemd service, and Nginx runtime config.
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
python3 -m pytest -q backend/tests

cd frontend-trading && npm run build
cd frontend-notes && npm run build
cd frontend-monitor && npm run build
cd frontend-ledger && npm run build
```

## Deployment
Production deployment now uses direct server deployment by default. Clone the repository to the server, keep the working tree under `/opt/tradingRecords`, build each frontend in place, run the FastAPI backend through `systemd`, and let host Nginx serve the portal, SPA bundles, and `/api/*` proxy.

```bash
bash deploy/setup.sh
bash deploy/update.sh
```

- `deploy/setup.sh`: first-time server bootstrap. Installs runtime dependencies (including Node.js 22.22.0), creates the production virtualenv under `/opt/tradingRecordsData/venv`, builds all frontend apps, installs Nginx config, and enables the `trading` systemd service.
- `deploy/cert-renew.sh`: runs `certbot renew` and reloads Nginx after a successful renewal.
- `deploy/trading-cert-renew.service` + `deploy/trading-cert-renew.timer`: twice-daily renewal check through `systemd timer`; `deploy/setup.sh` installs and enables them automatically.
- `deploy/update.sh`: routine server update. Pulls the latest code, ensures Node.js 22.22.0 or newer, refreshes backend dependencies in `/opt/tradingRecordsData/venv`, rebuilds all frontend apps, syncs portal files, reloads Nginx, and restarts the `trading` service.
- `deploy/trading.service`: systemd unit that runs `uvicorn` from `/opt/tradingRecordsData/venv` and keeps uploads outside the repo through `UPLOAD_DIR=/opt/tradingRecordsData/uploads`.
- `deploy/nginx.conf`: host-level Nginx config that serves `/`, `/trading/`, `/notes/`, `/monitor/`, `/ledger/`, and proxies `/api/*` to `127.0.0.1:8000`.

For existing servers that already have Let's Encrypt certificates, you can force an immediate renewal check with:

```bash
bash deploy/cert-renew.sh
systemctl status trading-cert-renew.timer
```

## Docs & Validation
- [docs/MODULE_REGISTRY.md](./docs/MODULE_REGISTRY.md)
- [docs/API_STYLE.md](./docs/API_STYLE.md)
- [docs/BACKEND_STRUCTURE.md](./docs/BACKEND_STRUCTURE.md)
- [docs/DEPENDENCY_POLICY.md](./docs/DEPENDENCY_POLICY.md)
- [docs/SECURITY.md](./docs/SECURITY.md)
- [scripts/check_all.sh](./scripts/check_all.sh)
- [scripts/check_deploy.sh](./scripts/check_deploy.sh)
- [scripts/check_naming.sh](./scripts/check_naming.sh)
- [scripts/check_router_style.py](./scripts/check_router_style.py)
- [scripts/check_runtime_boundaries.py](./scripts/check_runtime_boundaries.py)
- [scripts/check_runtime_size.py](./scripts/check_runtime_size.py)
- [docs/ledger-smoke-checklist.md](./docs/ledger-smoke-checklist.md)
- [scripts/ledger-smoke.sh](./scripts/ledger-smoke.sh)
- [README.zh-CN.md](./README.zh-CN.md)
