[中文文档](./README.zh-CN.md)

# Trading Records Workspace

## 1. Project Name
Trading Records Workspace

## 2. Overview
This repository is a self-hosted multi-app workspace for trading operations. It includes:
- A trading records and analytics app
- A notes and to-do app
- A server monitoring dashboard
- A portal + login pages
- A FastAPI backend serving all APIs

The backend uses SQLite and stores runtime data under `backend/data`.

## 3. Core Modules
- `backend`: FastAPI application, domain models, API endpoints, auth, data migration, monitoring metrics.
- `frontend`: Trading app (records, analytics, review sessions, trade plans, knowledge items, broker maintenance).
- `frontend-notes`: Notes app (diary/doc notes, rich-text editor, wiki links, recycle bin, to-do).
- `frontend-monitor`: Website monitoring app (server monitor, site availability checks, user admin, audit logs).
- `portal`: Static homepage and login page.
- `deploy`: Production scripts (`setup.sh`, `update.sh`), `nginx` config, `systemd` service.
- `dev.sh`: Unified local development orchestration script.

## 4. Key Features
- Trade CRUD and filters (`/api/trades`), count/statistics/analytics endpoints.
- Paste-based trade import (`/api/trades/import-paste`) with staged validation and open/close matching logic.
- Open position view (`/api/trades/positions`).
- Structured trade review taxonomy + per-trade review metadata.
- Research content modal now includes standard review fields (entry thesis, evidence, boundary, management, exit reason) by default.
- Research content editor supports WYSIWYG text styling (bold/italic/highlight background) with image paste/upload.
- Fixed issue where pasting/uploading images in the research editor could clear unsaved text in the current session.
- Trade source metadata layer and source fallback parsing from legacy notes.
- Review sessions as first-class objects (`/api/review-sessions`) with linked trades and filtered-slice generation.
- Trade plans (`/api/trade-plans`) with enforced status transitions and links to trades/review sessions.
- Knowledge base (`/api/knowledge-items`) with category/tag/status filtering and multi-doc note links.
- Knowledge/review workspaces use folder-style grouped sidebars with single-expand behavior and compact item cards.
- Trading / review / plan / maintenance workspaces now use a narrower grouped left panel (desktop `xl`), with more room for the main editor/content area.
- UI readability pass: lighter non-white workspace background and stronger visual emphasis for key fields (stat titles, labels, dropdowns, action buttons, workspace headers, and trade-detail metadata sections).
- Portal homepage readability pass: added a global ultra-light white overlay, softened text lift shadows, switched the daily poem section to traditional vertical layout, removed the poem blur card, and improved bottom nav subtitle contrast/size.
- Daily poem typography refinement: reorganized into right-to-left vertical columns (title/right, poem/body, inscription/left), moved attribution to the left as a signature line, and increased body spacing (`letter-spacing`/`line-height`) for calmer long-short sentence rhythm.
- Trading app default landing route now opens dashboard (`/trading/` -> `/trading/dashboard`) instead of trade list.
- Daily poem expand/collapse is now a compact icon button under the refresh icon, aligned in the same vertical control column.
- Sidebar ordering supports priority-first + maintenance-time ordering (same priority sorted by earlier update time first).
- Trading recycle bin for five domains: trades, knowledge items, brokers, review sessions, trade plans (`/api/recycle/*` restore/purge endpoints).
- Notebook/notes/todo system with recycle bin and backlinks/search/calendar endpoints.
- Image upload and serving (`/api/upload`, `/api/uploads/{filename}`).
- Daily poem endpoint with remote fetch + local fallback cache (`/api/poem/daily`).
- Multi-user auth with fixed roles (`admin` / `user`), where `xiaoyao` is the admin account after migration.
- Role-domain data isolation on business entities via `owner_role` (`admin` can view all domains; `user` sees only `user` domain).
- Website monitor app with submodules: server monitor, site availability checks, user management, and browse/audit logs.
- Monitor access control is enforced both in frontend visibility and backend authorization (`user` gets `403` on monitor/admin APIs).
- User management supports editing role/password and deleting user accounts (reserved admin account protected).
- Site monitor target CRUD + polling result history APIs (`/api/monitor/sites*`).
- Browse tracking APIs (`/api/audit/track`, `/api/audit/logs`) with 180-day retention, excluding admin records; logs support pagination/filtering/deletion and return CN time + Chinese labels.
- Server monitor APIs (`/api/monitor/realtime`, `/api/monitor/history`) backed by `psutil` and restricted to admin.
- Cookie-based authentication middleware for `/api/*` in non-dev mode.
- `./dev.sh down` orphan cleanup is hardened for mixed shell/Windows scenarios (broader Vite process matching + process-tree termination).

## 5. Tech Stack
- Backend: Python, FastAPI, SQLAlchemy, Pydantic, Uvicorn
- Storage: SQLite (`backend/data/trading.db`)
- Monitoring: `psutil`
- HTTP/data parsing helpers: `httpx`, `ebooklib`, `beautifulsoup4`
- Frontend apps: React + Vite + Axios + Ant Design
- Charts: `recharts`
- Notes editor: Tiptap ecosystem (`@tiptap/*`, `tiptap-markdown`)
- Deployment: Nginx + systemd + shell scripts

## 6. Architecture Overview
- Browser traffic is routed by Nginx:
  - `/` -> `portal/index.html`
  - `/login` -> `portal/login.html`
  - `/trading/` -> `frontend/dist`
  - `/notes/` -> `frontend-notes/dist`
  - `/monitor/` -> `frontend-monitor/dist`
  - `/api/*` -> FastAPI (`127.0.0.1:8000`)
- FastAPI serves domain APIs, uploads, auth, poem, monitor data, and audit/user-admin endpoints.
- Authentication:
  - In `DEV_MODE=1`, APIs run with admin dev context.
  - In non-dev mode, `/api/*` requires a valid `session_token` cookie except auth whitelist routes.
  - User roles are persisted in DB table `users`; legacy `backend/data/auth.json` is auto-migrated to `xiaoyao/admin`.
- Data flow:
  - Persistent data stored in SQLite under `backend/data`.
  - Uploaded images stored under `backend/data/uploads`.
- Auth secret file is stored under `backend/data/.secret`; legacy `auth.json` is kept only for compatibility.

## 7. Directory Structure
```text
.
├─ backend/
│  ├─ main.py
│  ├─ auth.py
│  ├─ database.py
│  ├─ models.py
│  ├─ schemas.py
│  ├─ trade_review_taxonomy.py
│  ├─ trading/
│  │  ├─ analytics_service.py
│  │  ├─ import_service.py
│  │  ├─ knowledge_service.py
│  │  ├─ review_service.py
│  │  ├─ review_session_service.py
│  │  ├─ source_service.py
│  │  ├─ tag_service.py
│  │  └─ trade_plan_service.py
│  ├─ tests/
│  │  ├─ conftest.py
│  │  └─ test_*.py
│  └─ data/
│     ├─ trading.db
│     ├─ uploads/
│     └─ news_epub/
├─ frontend/
│  ├─ src/
│  │  ├─ api/
│  │  ├─ components/
│  │  ├─ features/trading/
│  │  ├─ pages/
│  │  └─ utils/
│  ├─ index.html
│  ├─ vite.config.js
│  └─ package.json
├─ frontend-notes/
│  ├─ src/
│  │  ├─ api/
│  │  ├─ components/
│  │  └─ utils/
│  ├─ index.html
│  ├─ vite.config.js
│  └─ package.json
├─ frontend-monitor/
│  ├─ src/
│  │  ├─ api.js
│  │  ├─ App.jsx
│  │  └─ main.jsx
│  ├─ index.html
│  ├─ vite.config.js
│  └─ package.json
├─ frontend-news/            # legacy directory, currently no package.json
├─ portal/
│  ├─ dev_server.py
│  ├─ index.html
│  └─ login.html
├─ deploy/
│  ├─ setup.sh
│  ├─ update.sh
│  ├─ remote-update.sh
│  ├─ nginx.conf
│  └─ trading.service
├─ AGENTS.md
├─ dev.sh
├─ README.md
└─ README.zh-CN.md
```

(`node_modules`, `dist`, `.dev-run`, and other generated files are omitted.)

## 8. Getting Started
Quick local start uses the repository-level script:

```bash
./dev.sh up
```

This starts backend + `portal` local dev gateway + all auto-discovered frontend dev servers (directories matching `frontend*` that contain `package.json` with a `dev` script), using tmux when available or background mode otherwise.
Open the portal at `http://127.0.0.1:5172` (or `PORTAL_DEV_PORT`).

## 9. Prerequisites
- Python 3
- Node.js + npm
- Optional: `tmux` (for multi-pane local development)
- Linux server requirements for deployment scripts: `nginx`, `systemd`

## 10. Installation
Install dependencies per module:

```bash
# backend
cd backend
pip install -r requirements.txt

# trading frontend
cd ../frontend
npm install

# notes frontend
cd ../frontend-notes
npm install

# monitor frontend
cd ../frontend-monitor
npm install
```

## 11. Environment Variables
The backend reads environment variables directly from process env (no dotenv loader in code).

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEV_MODE` | `0` | `1` bypasses API auth middleware for development. |
| `COOKIE_SECURE` | `1` when `DEV_MODE=0`, otherwise `0` | Controls `secure` flag on auth cookie. |
| `POEM_CACHE_TTL` | `1800` | Daily poem cache TTL in seconds. |
| `POEM_REMOTE_URL` | `https://v2.jinrishici.com/sentence` | Remote poem API URL. |
| `JINRISHICI_TOKEN` | empty | Optional token for poem API request header. |

A minimal `.env.example` is included at repository root.
Repository ignore rules keep `.env` / `.env.*` out of Git while preserving `.env.example`.

## 12. Available Scripts
Repository-level:
- `./dev.sh up`: start backend + `portal` local dev gateway + all auto-discovered `frontend*` dev services.
- `./dev.sh down`: stop all local services and force-clean leftover repo-local debug processes (`vite`/`npm run dev`, portal `dev_server.py`, and matching backend `uvicorn`).
- `./dev.sh down` on Windows bash (`Git Bash`/`MSYS`/`Cygwin`) includes an extra PowerShell fallback sweep to stop residual native `node/vite` dev processes.
- `./dev.sh status`: check tmux/background service status.
- `./dev.sh attach`: attach tmux session or tail logs.
- `./dev.sh restart`: restart all services.
- `DEV_LOG_MODE=none ./dev.sh up`: disable log files in background mode (`.dev-run/*.log`).
- `./dev.sh down`: auto-cleans all `.dev-run` pid/log files by default (including legacy/manual logs).
- `DEV_CLEAN_ON_DOWN=0 ./dev.sh down`: keep all `.dev-run` pid/log files when stopping services.
- `PORTAL_DEV_PORT=5172 ./dev.sh up`: override portal local entry port.
- `PORTAL_BACKEND_PORT=8000 PORTAL_TRADING_PORT=5173 PORTAL_NOTES_PORT=5174 PORTAL_MONITOR_PORT=5175 ./dev.sh up`: override portal upstream ports.

Frontend modules (for example `frontend`, `frontend-notes`, `frontend-monitor`):
- `npm run dev`
- `npm run build`
- `npm run preview`

Deployment scripts:
- `deploy/setup.sh`: first-time server setup.
- `deploy/update.sh`: pull latest code, install/build, update nginx config, restart services.
- `deploy/remote-update.sh`: trigger remote `deploy/update.sh` from local machine over SSH.

## 13. Development
Recommended workflow:
1. Install dependencies for all modules.
2. Set environment variables (or export from `.env.example`).
3. Run `./dev.sh up` from repo root.
4. Use `./dev.sh attach` to inspect logs.
5. Run backend tests before pushing:

```bash
pytest -q backend/tests
```

## 14. Production Build
Manual build sequence:

```bash
cd frontend && npm run build
cd ../frontend-notes && npm run build
cd ../frontend-monitor && npm run build
```

Backend runs with Uvicorn (no wheel/package build step in this repository).

## 15. Deployment Notes
Current deployment assets are Linux-oriented and expect `/opt/tradingRecords`:
- `deploy/trading.service` runs `python3 -m uvicorn main:app --host 127.0.0.1 --port 8000` in `/opt/tradingRecords/backend`.
- `deploy/nginx.conf` exposes portal/apps under `/`, `/trading/`, `/notes/`, `/monitor/`, and proxies `/api/`.
- `deploy/update.sh` performs `git pull`, installs backend deps, builds all frontends, updates portal files, and restarts `nginx` + `trading` service.
- When triggered by non-root users (for example `admin`), `deploy/update.sh` uses `sudo` for privileged steps (`nginx`/`systemctl`), so that user must have corresponding sudo permissions.
- Local one-command trigger (without manually logging into server):
  - `PROD_HOST=<server_ip> PROD_USER=admin bash deploy/remote-update.sh`

## 16. Database / Storage
- Main DB: `backend/data/trading.db` (SQLite).
- Uploads: `backend/data/uploads/`.
- Auth files:
  - `backend/data/auth.json` (hashed password with salt)
  - `backend/data/.secret` (token signing secret)
- Startup behavior in `backend/main.py`:
  - `Base.metadata.create_all(...)`
  - Legacy column migrations for existing SQLite tables
  - Legacy `reviews` data migration into `review_sessions` when conditions match

## 17. Monitoring / Server
Backend monitor endpoints:
- `GET /api/monitor/realtime`: system/cpu/memory/disk/network/process/service snapshot.
- `GET /api/monitor/history`: in-memory trend history sampled by a background thread every 5 seconds.

Frontend monitor app (`frontend-monitor`) polls these endpoints and renders dashboards/charts.

## 18. Usage Notes
- First-time auth setup requires `POST /api/auth/setup`; it initializes `xiaoyao` as the admin account.
- Frontend axios interceptors redirect `401` responses to `/login`.
- Admin APIs:
  - `GET/POST /api/admin/users`
  - `PUT /api/admin/users/{id}`
  - `DELETE /api/admin/users/{id}`
  - `POST /api/admin/users/{id}/toggle-active`
  - `POST /api/admin/users/{id}/reset-password`
- Monitor APIs:
  - `GET /api/monitor/realtime`, `GET /api/monitor/history` (admin-only)
  - `GET/POST /api/monitor/sites`, `PUT/DELETE /api/monitor/sites/{id}`
  - `GET /api/monitor/sites/{id}/results`
- Audit APIs:
  - `POST /api/audit/track`
  - `GET /api/audit/logs` (admin-only; supports `page/size/username/module/event_type/keyword/date_from/date_to`)
  - `DELETE /api/audit/logs/{id}` (admin-only)
- Notes module and trading research panels upload images through `/api/upload`.
- Knowledge item API fields:
  - `POST/PUT /api/knowledge-items`: optional `related_note_ids: number[]` for linked doc notes (`note_type=doc` only).
  - `GET /api/knowledge-items*`: returns `related_notes` (`id`, `title`, `note_type`, `updated_at`, `notebook_id`) for each item.
- Trading recycle APIs:
  - `GET /api/recycle/{trades|knowledge-items|trade-brokers|review-sessions|trade-plans}`
  - `POST /api/recycle/<resource>/{id}/restore`
  - `DELETE /api/recycle/<resource>/{id}/purge`
- Notes deep-link query params (`/notes/`):
  - `tab=doc|diary`
  - `noteId=<number>`
  - `anchor=<optional>`
- The repository collaboration convention in `AGENTS.md` requires:
  - Use `./dev.sh` for local debug flow.
  - Use `deploy/update.sh` for production update flow.
  - Check `frontend-notes` build before pushing.
  - Update both `README.md` and `README.zh-CN.md` before each push.

## 19. Roadmap
Conservative, codebase-driven near-term directions:
- Continue migrating legacy review paths toward `review_sessions` as the primary model.
- Incrementally clean Pydantic v2 deprecation warnings (`class Config` style currently used).
- Keep trade source metadata coverage high to reduce legacy note parsing dependency.

## 20. Contributing
- Keep changes aligned with existing module boundaries (`backend`, `frontend`, `frontend-notes`, `frontend-monitor`, `portal`, `deploy`).
- Validate affected frontend builds, especially `frontend-notes`.
- Run backend tests (`pytest -q backend/tests`) for API/domain changes.
- Follow repository collaboration rules in `AGENTS.md`.

## 21. License
Not specified.
