[English README](./README.md)

# Trading Records Workspace

## 1. 项目名称
Trading Records Workspace

## 2. 项目简介
这是一个自托管的多应用交易工作区仓库，包含：
- 交易记录与分析系统
- 笔记与待办系统
- 服务器监控面板
- 门户与登录静态页面
- 统一 FastAPI 后端

后端使用 SQLite，运行期数据默认落在 `backend/data`。

## 3. 核心模块
- `backend`：FastAPI 应用、领域模型、接口、鉴权、数据迁移、监控采样。
- `frontend`：交易前端（记录、分析、复盘会话、交易计划、知识库、券商维护）。
- `frontend-notes`：笔记前端（日记/文档、富文本编辑、Wiki 链接、回收站、待办）。
- `frontend-monitor`：监控前端（系统、进程、网络、磁盘、服务状态）。
- `portal`：门户首页与登录页。
- `deploy`：生产脚本（`setup.sh`、`update.sh`）、Nginx 配置、systemd 服务文件。
- `dev.sh`：本地联调统一编排脚本。

## 4. 主要功能
- 交易 CRUD 与筛选（`/api/trades`）、计数/统计/分析接口。
- 粘贴导入交易（`/api/trades/import-paste`），带分阶段校验与开平仓匹配。
- 持仓视图（`/api/trades/positions`）。
- 结构化交易复盘分类体系与单笔复盘元数据。
- 图文研究录入默认包含标准复盘字段（入场论点、证据、边界、管理动作、离场原因）。
- 图文研究编辑支持所见即所得文字样式（加粗/斜体/背景高亮）与图片粘贴上传。
- 交易来源元数据层，并兼容从旧 notes 文本回退提取来源。
- 复盘会话（`/api/review-sessions`）作为一等对象，支持关联交易和按筛选条件生成样本。
- 交易计划（`/api/trade-plans`）及状态流转校验，可关联交易与复盘会话。
- 知识库（`/api/knowledge-items`），支持分类/标签/状态筛选。
- 信息维护/复盘会话工作台左侧改为文件夹分组视图，支持单分类展开与紧凑条目展示。
- 文件夹内支持“优先级优先 + 维护时间”排序（同优先级按维护时间更早优先）。
- 交易模块回收站：成交记录、知识、券商、复盘会话、交易计划支持删除后恢复（`/api/recycle/*`）。
- 笔记本/笔记/待办系统，含回收站、反向链接、搜索、日历接口。
- 图片上传与访问（`/api/upload`、`/api/uploads/{filename}`）。
- 每日诗词接口，支持远程获取 + 本地兜底缓存（`/api/poem/daily`）。
- 服务器监控接口（`/api/monitor/realtime`、`/api/monitor/history`），基于 `psutil`。
- 非开发模式下 `/api/*` 的 Cookie 鉴权中间件。

## 5. 技术栈
- 后端：Python、FastAPI、SQLAlchemy、Pydantic、Uvicorn
- 存储：SQLite（`backend/data/trading.db`）
- 监控采集：`psutil`
- 网络/解析辅助：`httpx`、`ebooklib`、`beautifulsoup4`
- 前端：React + Vite + Axios + Ant Design
- 图表：`recharts`
- 笔记编辑器：Tiptap 生态（`@tiptap/*`、`tiptap-markdown`）
- 部署：Nginx + systemd + Shell 脚本

## 6. 架构说明
- 浏览器流量由 Nginx 路由：
  - `/` -> `portal/index.html`
  - `/login` -> `portal/login.html`
  - `/trading/` -> `frontend/dist`
  - `/notes/` -> `frontend-notes/dist`
  - `/monitor/` -> `frontend-monitor/dist`
  - `/api/*` -> FastAPI（`127.0.0.1:8000`）
- FastAPI 负责业务接口、上传、鉴权、诗词与监控数据。
- 鉴权策略：
  - `DEV_MODE=1` 时跳过 API 鉴权中间件。
  - 非开发模式下，除白名单鉴权接口外，`/api/*` 需有效 `session_token` Cookie。
- 数据流：
  - 持久化数据进 SQLite（`backend/data`）。
  - 上传图片落地到 `backend/data/uploads`。
  - 鉴权账号与签名密钥文件保存在 `backend/data`。

## 7. 目录结构
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
├─ frontend-news/            # 历史遗留目录，当前无 package.json
├─ portal/
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

（已省略 `node_modules`、`dist`、`.dev-run` 等构建/运行期产物目录。）

## 8. 快速开始
本地联调建议直接使用仓库根脚本：

```bash
./dev.sh up
```

该命令会拉起 backend + 自动发现的全部 frontend 开发服务（匹配 `frontend*` 目录且 `package.json` 中含 `dev` 脚本）；有 tmux 则用 tmux，没有则后台运行。

## 9. 前置要求
- Python 3
- Node.js + npm
- 可选：`tmux`（多窗口联调）
- 生产脚本运行环境：Linux + `nginx` + `systemd`

## 10. 安装方式
按模块安装依赖：

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

## 11. 环境变量
后端直接读取进程环境变量（代码里没有 dotenv 自动加载）。

| 变量名 | 默认值 | 作用 |
| --- | --- | --- |
| `DEV_MODE` | `0` | 设为 `1` 时跳过 API 鉴权中间件，便于本地开发。 |
| `COOKIE_SECURE` | `DEV_MODE=0` 时为 `1`，否则为 `0` | 控制登录 Cookie 的 `secure` 标记。 |
| `POEM_CACHE_TTL` | `1800` | 每日诗词缓存秒数。 |
| `POEM_REMOTE_URL` | `https://v2.jinrishici.com/sentence` | 远程诗词接口地址。 |
| `JINRISHICI_TOKEN` | 空 | 诗词接口可选请求令牌。 |

仓库根目录已补充最小可用 `.env.example`。
仓库忽略规则会屏蔽 `.env` / `.env.*`，并保留 `.env.example` 模板。

## 12. 常用脚本
仓库级：
- `./dev.sh up`：启动 backend + 自动发现的全部 `frontend*` 本地开发服务。
- `./dev.sh down`：停止全部本地服务，并兜底清理仓库内残留调试进程（`vite`/`npm run dev` 及匹配的后端 `uvicorn`）。
- `./dev.sh status`：查看 tmux/后台进程状态。
- `./dev.sh attach`：附着 tmux 或跟随日志。
- `./dev.sh restart`：重启全部服务。
- `./dev.sh down`：默认会自动全量清理 `.dev-run` 下全部 `pid/log` 文件（含历史/手工日志）。
- `DEV_CLEAN_ON_DOWN=0 ./dev.sh down`：停止服务时保留 `.dev-run` 下全部 `pid/log` 文件。

前端子应用（如 `frontend`、`frontend-notes`、`frontend-monitor`）：
- `npm run dev`
- `npm run build`
- `npm run preview`

部署脚本：
- `deploy/setup.sh`：服务器首次部署。
- `deploy/update.sh`：拉取更新、安装/构建、更新 Nginx、重启服务。
- `deploy/remote-update.sh`：在本地通过 SSH 触发远端 `deploy/update.sh`。

## 13. 本地开发
推荐流程：
1. 安装各模块依赖。
2. 设置环境变量（可参考 `.env.example`）。
3. 在仓库根运行 `./dev.sh up`。
4. 用 `./dev.sh attach` 查看日志。
5. 推送前运行后端测试：

```bash
pytest -q backend/tests
```

## 14. 生产构建
手动构建顺序：

```bash
cd frontend && npm run build
cd ../frontend-notes && npm run build
cd ../frontend-monitor && npm run build
```

后端以 Uvicorn 直接运行，本仓库没有单独打包步骤。

## 15. 部署说明
当前部署资源面向 Linux，默认路径 `/opt/tradingRecords`：
- `deploy/trading.service` 在 `/opt/tradingRecords/backend` 启动 `python3 -m uvicorn main:app --host 127.0.0.1 --port 8000`。
- `deploy/nginx.conf` 暴露门户和三个前端子路径，并将 `/api/` 反向代理到后端。
- `deploy/update.sh` 会执行 `git pull`、安装后端依赖、构建三套前端、同步门户页面、重启 `nginx` 与 `trading` 服务。
- 若通过非 root 用户（如 `admin`）触发，`deploy/update.sh` 会在特权步骤（`nginx`/`systemctl`）自动走 `sudo`，因此该用户需具备相应 sudo 权限。
- 本地一条命令触发远端更新（无需先登录服务器）：
  - `PROD_HOST=<服务器IP> PROD_USER=admin bash deploy/remote-update.sh`

## 16. 数据库或存储说明
- 主数据库：`backend/data/trading.db`（SQLite）。
- 上传文件目录：`backend/data/uploads/`。
- 鉴权文件：
  - `backend/data/auth.json`（带盐哈希密码）
  - `backend/data/.secret`（Token 签名密钥）
- `backend/main.py` 启动阶段行为：
  - `Base.metadata.create_all(...)`
  - 针对已有 SQLite 表执行遗留字段迁移
  - 在条件满足时将旧 `reviews` 数据迁移到 `review_sessions`

## 17. 监控或服务相关说明
后端监控接口：
- `GET /api/monitor/realtime`：系统/CPU/内存/磁盘/网络/进程/服务快照。
- `GET /api/monitor/history`：后台线程每 5 秒采样一次的内存历史序列。

`frontend-monitor` 周期轮询上述接口并展示图表面板。

## 18. 使用说明或注意事项
- 首次使用需先调用 `POST /api/auth/setup` 初始化账号，否则无法登录。
- 前端 Axios 拦截 `401` 并跳转 `/login`。
- 笔记编辑器与交易研究面板图片都通过 `/api/upload` 上传。
- 交易模块回收站接口：
  - `GET /api/recycle/{trades|knowledge-items|trade-brokers|review-sessions|trade-plans}`
  - `POST /api/recycle/<resource>/{id}/restore`
  - `DELETE /api/recycle/<resource>/{id}/purge`
- `AGENTS.md` 协作约定要求：
  - 本地调试统一使用 `./dev.sh`。
  - 生产更新统一使用 `deploy/update.sh`。
  - 推送前优先检查 `frontend-notes` 可构建。
  - 每次推送前同步更新 `README.md` 与 `README.zh-CN.md`。

## 19. 后续计划
基于当前代码形态的保守方向：
- 继续收敛遗留 `reviews` 路径，逐步以 `review_sessions` 作为核心复盘模型。
- 逐步消除 Pydantic v2 兼容告警（目前仍使用 `class Config` 形式）。
- 提高 `trade_source_metadata` 覆盖率，减少对旧 notes 文本解析的依赖。

## 20. 贡献说明
- 按现有模块边界提交改动（`backend`、`frontend`、`frontend-notes`、`frontend-monitor`、`portal`、`deploy`）。
- 校验受影响前端构建，尤其是 `frontend-notes`。
- 涉及 API/领域逻辑时运行 `pytest -q backend/tests`。
- 遵守仓库 `AGENTS.md` 约定。

## 21. 许可证
未明确声明。
