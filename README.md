# 骁遥骑士 · 个人多模块工作台

一个运行在 FastAPI + React 多前端架构上的个人系统仓库，核心方向是将交易记录从“台账录入”扩展为“记录-复盘-研究-改进”的持续工作流。

当前仓库包含四个业务前端（交易、笔记、新闻、监控）与一个统一后端，生产环境通过 Nginx + systemd 部署，本地通过 `./dev.sh` 一键调试。

## 项目概览

### 这个仓库是什么

- 一个真实使用中的个人工作台系统，而非单页 demo。
- 以交易记录子系统为主线，同时承载知识笔记、新闻阅读与服务器监控。
- 后端使用单体 FastAPI 服务统一提供 API，前端按业务拆分为多个 Vite 应用。

### 适用对象

- 交易者：希望把成交记录、单笔复盘、周期复盘、样本关联与知识沉淀放在同一系统内。
- 开发者/维护者：需要在一个仓库中持续演进多模块产品，并保持数据模型与流程一致性。

### 当前范围

- 覆盖交易记录、结构化复盘、来源元数据、周期复盘、知识条目维护、分析看板。
- 覆盖日记/文档/待办/回收站、新闻同步与翻译、服务器指标监控。
- 仍在持续演进，保留一部分兼容路径（如交易 legacy notes 字段）。

## 核心模块

### 交易记录与研究工作台（`/trading/`）

交易子系统当前不是简单 CRUD 台账，已形成“记录 + 复盘 + 研究”组合：

- 成交流水管理：交易录入、列表筛选、批量编辑、批量删除。
- 粘贴导入：支持期货日结单粘贴导入与开平匹配。
- 单笔结构化复盘：`TradeReview` 模型（机会结构、优势来源、失败类型、复盘结论、研究备注等）。
- 来源元数据：`TradeSourceMetadata` 模型（券商、来源标签、导入通道、解析版本等），metadata-first 展示。
- 周期/主题复盘：`Review` + `ReviewTradeLink` 支持多交易样本关联（best/worst/representative/linked）。
- 信息维护：知识条目（`KnowledgeItem`）与券商来源维护并存。
- 交易分析仪表盘：overview/time series/dimensions/behavior/coverage/positions 多维视角。

### 知识笔记（`/notes/`）

- 日记与文档分区管理，支持嵌套文件夹。
- 富文本编辑（TipTap）与图片上传。
- Read mode markdown code-block rendering uses compact typography for dense technical reading while preserving wikilink/image-lightbox behavior.
- 全文搜索、双向链接（wikilink/backlink）、日历与历史今日。
- 待办与回收站为独立工作流。

### 新闻实事（`/news/`）

- Economist 最新期同步、EPUB 抽取、分块翻译与进度追踪。
- 今日新闻聚合（多分类 RSS）与正文抓取。

### 服务器监控（`/monitor/`）

- 实时系统指标：CPU、内存、磁盘、网络、进程、服务状态。
- 历史趋势：后台每 5 秒采样，前端轮询展示。

### 门户与登录（`/`、`/login`）

- 静态门户页面聚合业务入口。
- 自定义会话认证，未登录访问 API 会返回 401。

## 交易子系统模型与定位

交易域当前核心模型（见 `backend/models.py`）：

- `Trade`：成交与持仓语义（流水层）。
- `TradeReview`：单笔结构化复盘语义（主复盘路径）。
- `TradeSourceMetadata`：来源/券商/导入语义（主来源路径）。
- `Review` + `ReviewTradeLink`：多笔交易的周期/主题复盘与样本关联。
- `KnowledgeItem`：交易相关知识沉淀（形态、环境、执行、风控等）。
- `TagTerm` + link tables：`TradeReview` / `Review` / `KnowledgeItem` 的统一标签关联。

说明：

- `notes`、`review_note`、旧标签文本列仍保留，用于兼容历史数据。
- active 路径以显式模型为主，不再仅依赖自由文本解析。

## 关键工作流

### 1. 导入交易记录（期货日结单）

1. 在交易工作台打开“粘贴导入”。
2. 粘贴 10 列制表符数据（支持含表头或无表头）。
3. 后端执行分阶段处理：解析/去重 -> 平仓预检 -> 开平入库与匹配。
4. 返回 `inserted/skipped/errors`，并同步写入来源元数据（`import_channel=paste_import`）。

### 2. 检查与维护交易记录

1. 在记录页进行分页、筛选、批量操作。
2. 在详情抽屉查看单笔交易、结构化复盘、来源信息。
3. 默认读态，进入编辑后再保存（read/edit 双态）。

### 3. 单笔复盘与来源维护

- 单笔复盘通过 `/api/trades/{id}/review` 维护，taxonomy 使用 canonical key。
- 来源信息通过 `/api/trades/{id}/source-metadata` 维护。
- 旧 `notes` 来源解析仅作为 fallback。

### 4. 周期复盘与样本关联

1. 在复盘工作台创建日/周/月或自定义复盘。
2. 通过远程检索接口 `/api/trades/search-options` 关联样本交易。
3. 保存 `Review` 主体与 `ReviewTradeLink` 关系。
4. 在只读态以内容卡片查看关联样本摘要。

### 5. 分析与研究

- 仪表盘读取 `/api/trades/analytics`，展示：
  - 收益与效率指标（含 Sharpe、最大回撤、手续费/净利润比等）
  - 时间序列（日/周/月）
  - 品种/来源/结构化复盘维度
  - 行为分布与覆盖率
  - 当前持仓视角

### 6. 复盘结论沉淀为知识

- 在“信息维护 -> 知识库”记录可复用经验（category/status/priority/tags/next action）。
- 与周期复盘形成“结论 -> 条目 -> 后续执行”的闭环。

## 技术栈

### 后端

- Python
- FastAPI
- SQLAlchemy
- SQLite
- `psutil`, `httpx`, `ebooklib`, `beautifulsoup4`

### 前端

- `frontend`（交易）：React 19 + Vite 8 + Ant Design 6 + Recharts 3
- `frontend-notes`（笔记）：React 19 + Vite 8 + Ant Design 6 + TipTap
- `frontend-news`（新闻）：React 19 + Vite 8 + Ant Design 6
- `frontend-monitor`（监控）：React 18 + Vite 6 + Ant Design 5 + Recharts 2

### 部署

- Nginx（静态资源 + 反向代理）
- systemd（`trading.service`）

## 代码结构

```text
program/
├── backend/
│   ├── main.py                      # FastAPI 入口与路由
│   ├── models.py                    # ORM 数据模型
│   ├── schemas.py                   # Pydantic schema
│   ├── auth.py                      # 认证与 token
│   ├── database.py                  # SQLite 连接
│   ├── trading/                     # 交易域服务拆分（analytics/import/review/source/knowledge/tag）
│   └── tests/                       # 后端测试（交易域为主）
├── frontend/                        # 交易前端
│   └── src/features/trading/        # 交易工作台与分析组件
├── frontend-notes/                  # 笔记前端
├── frontend-news/                   # 新闻前端
├── frontend-monitor/                # 监控前端
├── portal/                          # 门户与登录静态页
├── deploy/                          # 部署脚本、Nginx、systemd 配置
├── docs/                            # 交易域架构/审计/演进文档
└── dev.sh                           # 本地一键调试脚本
```

## 本地开发

### 环境要求

- Python 3.10+
- Node.js 18+
- npm
- 可选：tmux（`./dev.sh` 自动优先使用）

### 安装依赖

```bash
cd backend && pip3 install -r requirements.txt
cd ../frontend && npm install
cd ../frontend-notes && npm install
cd ../frontend-news && npm install
cd ../frontend-monitor && npm install
```

### 一键启动（推荐）

```bash
./dev.sh up
```

常用命令：

```bash
./dev.sh status
./dev.sh attach
./dev.sh down
./dev.sh restart
```

### 手动启动（多终端）

```bash
# backend
cd backend
DEV_MODE=1 python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# trading frontend
cd frontend && npm run dev

# notes frontend
cd ../frontend-notes && npm run dev

# news frontend
cd ../frontend-news && npm run dev

# monitor frontend
cd ../frontend-monitor && npm run dev
```

本地访问地址：

- 交易：`http://localhost:5173/trading/`
- 笔记：`http://localhost:5174/notes/`
- 监控：`http://localhost:5175/monitor/`
- 新闻：`http://localhost:5176/news/`

## 配置与环境变量

### 核心运行参数

- `DEV_MODE=1`：开发模式，跳过 API 登录校验。
- `COOKIE_SECURE`：控制登录 cookie 的 secure 属性（默认开发 0、非开发 1）。

### 新闻翻译相关

- `TRANSLATE_PROVIDER`：`auto` / `deepseek` / `openai`
- `DEEPSEEK_API_KEY` / `OPENAI_API_KEY`
- `OPENAI_BASE_URL` / `OPENAI_MODEL`
- `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` / `DEEPSEEK_MODELS`
- `TRANSLATE_MAX_WORKERS`

### 新闻抓取相关

- `ECONOMIST_REPO` / `ECONOMIST_BRANCH`
- `TODAY_NEWS_CACHE_TTL`

### 诗词接口（门户）

- `POEM_REMOTE_URL`
- `JINRISHICI_TOKEN`
- `POEM_CACHE_TTL`

## 数据与初始化行为

- 主库：`backend/data/trading.db`
- 启动即执行 `Base.metadata.create_all()` 自动建表。
- 启动时包含部分兼容迁移（列缺失时自动 `ALTER TABLE`）。
- 初次启动若无笔记本，会自动创建默认“日记本/文档”。
- 上传文件目录：`backend/data/uploads/`
- 新闻数据目录：`backend/data/news_epub/`

## 测试与验证

### 后端测试

```bash
cd backend
pytest -q
```

现有测试重点覆盖：

- 导入与匹配保护行为（characterization）
- 结构化复盘与 taxonomy
- 来源元数据与检索
- 交易分析指标
- 周期复盘关联交易
- 知识条目域行为

### 前端构建检查

```bash
cd frontend && npm run build
cd ../frontend-notes && npm run build
cd ../frontend-news && npm run build
cd ../frontend-monitor && npm run build
```

协作约定（见 `AGENTS.md`）：

- 推送前优先检查 `frontend-notes` 与 `frontend-news` 可构建。
- 本地调试统一使用 `./dev.sh`。
- 生产更新统一使用 `deploy/update.sh`。

## API 概览（按域）

完整实现请以 `backend/main.py` 为准。以下列出当前主要路由分组：

### 认证与会话

- `POST /api/auth/setup`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/check`

### 交易与分析

- 交易 CRUD：`/api/trades`、`/api/trades/{id}`
- 导入与持仓：`/api/trades/import-paste`、`/api/trades/positions`
- 列表辅助：`/api/trades/count`、`/api/trades/sources`、`/api/trades/search-options`
- 统计分析：`/api/trades/statistics`、`/api/trades/analytics`
- 单笔复盘：`/api/trades/{id}/review`、`/api/trade-review-taxonomy`
- 来源元数据：`/api/trades/{id}/source-metadata`

### 复盘与知识

- 周期复盘：`/api/reviews`、`/api/reviews/{id}`
- 样本关联：`PUT /api/reviews/{id}/trade-links`
- 知识条目：`/api/knowledge-items`、`/api/knowledge-items/categories`
- 券商维护：`/api/trade-brokers`

### 笔记系统

- 笔记本：`/api/notebooks`
- 笔记：`/api/notes`、`/api/notes/stats`、`/api/notes/search`
- 链接能力：`/api/notes/resolve-link`、`/api/notes/{id}/backlinks`
- 日记视图：`/api/notes/diary-tree`、`/api/notes/diary-summaries`、`/api/notes/calendar`、`/api/notes/history-today`
- 回收站：`/api/recycle/notes*`
- 待办：`/api/todos`

### 新闻与监控

- 新闻：`/api/news/sync`、`/api/news/issues*`、`/api/news/today`、`/api/news/article-content`
- 监控：`/api/monitor/realtime`、`/api/monitor/history`
- 门户诗词：`/api/poem/daily`

### 上传

- `POST /api/upload`
- `GET /api/uploads/{filename}`

## 部署

- 首次部署：`deploy/setup.sh`
- 日常更新：`deploy/update.sh`
- 服务定义：`deploy/trading.service`
- Nginx 配置：`deploy/nginx.conf`

生产默认形态：

- Nginx 暴露门户与四个前端路由前缀。
- `/api/*` 反向代理到 `127.0.0.1:8000`。
- FastAPI 由 systemd 管理。

## 当前成熟度与边界

### 已相对稳定

- 交易导入与开平匹配保护行为。
- 交易列表/详情/结构化复盘/来源元数据主路径。
- 周期复盘与样本关联基础能力。
- 交易分析看板与关键指标口径。

### 仍在演进

- 交易域逻辑从 `main.py` 向 `backend/trading/*` 继续拆分。
- 历史兼容字段（`notes`、`review_note`、旧 tags 文本列）仍保留，尚未完全退场。
- UI 仍以单用户场景为主，权限分层、审计追踪、自动化迁移工具链尚未系统化。

## 近期演进方向（基于现有代码与文档）

- 继续强化 trading workstation 的领域分层与模块内聚。
- 持续保持 metadata-first 与 structured-review-first，同时兼容历史数据。
- 逐步完善测试覆盖与行为保护清单，降低后续重构风险。

## 2026-04 Sprint: Rich Research + Favorites/Rating

### Domain model changes
- `Trade`
  - `is_favorite: boolean`
  - `star_rating: integer | null (1..5)`
- `TradeReview`
  - `research_notes: text (HTML rich research content)`
  - For legacy plain-text payloads, frontend/backend rendering keeps compatibility by converting plain text to readable HTML blocks.
- `Review`
  - `is_favorite: boolean`
  - `star_rating: integer | null (1..5)`
  - `research_notes: text (HTML rich research content)`

### Research-content ownership rule
- Single-trade rich research content is primarily stored in `TradeReview`.
- Periodic/themed rich research content is primarily stored in `Review`.
- `Trade` entity remains focused on trade facts/signals and should not become a mixed research text container.

### API additions
- Trade list/count (`/api/trades`, `/api/trades/count`) supports:
  - `is_favorite`
  - `min_star_rating`
  - `max_star_rating`
  - `/api/trades` additionally supports: `sort_by=updated_at|star_rating`, `sort_order=asc|desc`
- Review list (`/api/reviews`) supports:
  - `is_favorite`
  - `min_star_rating`
  - `max_star_rating`
  - `sort_by=updated_at|star_rating`
  - `sort_order=asc|desc`

### UX model
- Trade detail and Review detail both support rich research content with:
  - image upload/paste
  - manual image width adjustment (persisted in HTML)
  - strong read-only card rendering
  - read-only zoom via image preview group
- Favorites and star ratings are visible in list + detail and usable for daily filtering.
