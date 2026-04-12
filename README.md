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
- `frontend-monitor`: Monitoring app (system, process, network, disk, service status).
- `portal`: Static homepage and login page.
- `deploy`: Production scripts (`setup.sh`, `update.sh`), `nginx` config, `systemd` service.
- `dev.sh`: Unified local development orchestration script.

## 4. Key Features
- Trade CRUD and filters (`/api/trades`), count/statistics/analytics endpoints.
- Paste-based trade import (`/api/trades/import-paste`) with staged validation and open/close matching logic.
- Open position view (`/api/trades/positions`).
- Structured trade review taxonomy + per-trade review metadata.
- Trade source metadata layer and source fallback parsing from legacy notes.
- Review sessions as first-class objects (`/api/review-sessions`) with linked trades and filtered-slice generation.
- Trade plans (`/api/trade-plans`) with enforced status transitions and links to trades/review sessions.
- Knowledge base (`/api/knowledge-items`) with category/tag/status filtering.
- Notebook/notes/todo system with recycle bin and backlinks/search/calendar endpoints.
- Image upload and serving (`/api/upload`, `/api/uploads/{filename}`).
- Daily poem endpoint with remote fetch + local fallback cache (`/api/poem/daily`).
- Server monitor APIs (`/api/monitor/realtime`, `/api/monitor/history`) backed by `psutil`.
- Cookie-based authentication middleware for `/api/*` in non-dev mode.

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
- FastAPI serves domain APIs, uploads, auth, poem, and monitor data.
- Authentication:
  - In `DEV_MODE=1`, API auth middleware is bypassed.
  - In non-dev mode, `/api/*` requires a valid `session_token` cookie except auth whitelist routes.
- Data flow:
  - Persistent data stored in SQLite under `backend/data`.
  - Uploaded images stored under `backend/data/uploads`.
  - Auth credential and secret files stored under `backend/data`.

## 7. Directory Structure
```text
.
├─ backend/
│  ├─ main.py
│  ├─ models.py
│  ├─ schemas.py
│  ├─ database.py
│  ├─ auth.py
│  ├─ trading/
│  └─ tests/
├─ frontend/
├─ frontend-notes/
├─ frontend-monitor/
├─ portal/
├─ deploy/
├─ dev.sh
├─ README.md
└─ README.zh-CN.md
```

## 8. Getting Started
Quick local start uses the repository-level script:

```bash
./dev.sh up
```

This starts backend + three frontend dev servers (tmux if available, otherwise background mode).

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

## 12. Available Scripts
Repository-level:
- `./dev.sh up`: start all local services.
- `./dev.sh down`: stop all local services.
- `./dev.sh status`: check tmux/background service status.
- `./dev.sh attach`: attach tmux session or tail logs.
- `./dev.sh restart`: restart all services.

Frontend modules (`frontend`, `frontend-notes`, `frontend-monitor`):
- `npm run dev`
- `npm run build`
- `npm run preview`

Deployment scripts:
- `deploy/setup.sh`: first-time server setup.
- `deploy/update.sh`: pull latest code, install/build, update nginx config, restart services.

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
- First-time auth setup requires `POST /api/auth/setup` before login is possible.
- Frontend axios interceptors redirect `401` responses to `/login`.
- Notes module and trading research panels upload images through `/api/upload`.
- The repository collaboration convention in `AGENTS.md` requires:
  - Use `./dev.sh` for local debug flow.
  - Use `deploy/update.sh` for production update flow.
  - Check `frontend-notes` build before pushing.
  - Update README + interface list when changing notes module behavior.

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
