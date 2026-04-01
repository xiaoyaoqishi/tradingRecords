# 骁遥骑士 · 个人工作台

部署于阿里云 ECS 的个人工作平台，包含交易记录复盘系统和知识笔记模块。

---

## 系统架构

```
浏览器 ──► Nginx (80) ──┬── /login        → 登录页 (静态 HTML，山水风格)
                        ├── /             → 首页门户 (静态 HTML，山水风格)
                        ├── /trading/*    → 交易前端 (React SPA)
                        ├── /notes/*      → 笔记前端 (React SPA，eDiary 风格)
                        ├── /api/uploads/ → 图片文件 (静态资源)
                        └── /api/*        → FastAPI 后端 (127.0.0.1:8000)
                                               │
                                               ▼
                                          SQLite 数据库
```

| 层级 | 技术栈 | 说明 |
|------|--------|------|
| 前端 - 交易 | React 19 + Vite 8 + Ant Design 6 + Recharts 3 | 交易记录与复盘分析 |
| 前端 - 笔记 | React 19 + Vite 8 + Ant Design 6 + TipTap + lunar-javascript | eDiary 风格日记与文档管理 |
| 后端 | Python + FastAPI + SQLAlchemy | RESTful API + 图片上传存储 |
| 数据库 | SQLite | 数据文件：`backend/data/trading.db` |
| 门户 | 纯 HTML/CSS/JS | 山水风格首页 + 自定义登录页 |
| 部署 | Nginx + systemd | 反向代理、静态托管、进程管理 |

---

## 功能模块

### 首页门户

山水画风格首页，实时时钟，应用入口卡片（交易记录、知识笔记），右上角退出登录按钮。

### 登录认证

- 自定义登录页面（山水风格，与首页视觉统一）
- 密码输入支持 **显示/隐藏切换**（眼睛图标）
- 基于 HMAC 签名 Cookie 会话认证，登录状态保持 7 天
- 未登录时自动跳转登录页，支持 `?redirect=` 回跳
- 本地开发模式（`DEV_MODE=1`）跳过认证

### 交易记录系统（/trading/）

**四层记录体系**：

| 层次 | 解决的问题 | 核心字段 |
|------|-----------|---------|
| 成交流水层 | 发生了什么 | 日期、品种、合约、方向、价格、数量、盈亏、手续费 |
| 交易决策层 | 为什么做 | 入场/出场逻辑、策略类型、市场状态、止损/目标 |
| 行为纪律层 | 亏损归因 | 是否计划内、追单、扛单、重仓、报复性交易 |
| 标签与复盘层 | 如何改进 | 13 种错误标签、复盘一句话 |

- 可视化仪表盘：胜率、盈亏曲线、品种分布、策略统计、错误标签排行
- 交易列表：分页、筛选、排序、行内操作
- 三级复盘：日/周/月维度结构化复盘
- 多品种支持：期货、加密货币、股票、外汇

### 知识笔记系统（/notes/）

仿 eDiary 布局，左侧图标导航 + 内容区双栏设计。

**首页 Tab**：
- 公历 + 农历日期显示
- 自动定位获取当前天气（Open-Meteo API）+ 未来两天预报
- 知识笔记统计概览（日记/文档数量、总字数）
- 最近文档快速访问
- 日历备忘（含天气）
- 历史上的今天（往年同日日记）

**日记 Tab**：
- 自定义迷你日历（中文月份，有日记的日期橙色圆点标记）
- 标签分类筛选（全部日记、工作笔记、生活杂记、心情随笔）
- 「写今天的日记」按钮，自动生成标题：`天气图标 + 日期 + 星期 + 时间`
- 日期树形结构浏览（年 > 月 > 日）
- 右侧富文本编辑器

**文档 Tab**：
- 支持 **多级嵌套文件夹**（文件夹下可建子文件夹）
- 悬停显示操作按钮（新建文档、新建子文件夹、删除）
- 文件夹树 + 右侧编辑器

**富文本编辑器（TipTap）**：
- **字体选择**：宋体、黑体、楷体、仿宋、华文楷体、Arial、Georgia、Courier
- **字号选择**：12px ~ 32px
- **文字颜色**：9 种预设色板
- **背景颜色**：8 种高亮背景色 + 清除
- **格式**：加粗、斜体、下划线、删除线、上标、下标
- **标题**：H1 / H2 / H3
- **列表**：无序列表、有序列表、任务列表（☑）
- **引用 / 代码块**（支持 14 种语言语法高亮）
- **表格**：插入、增删行列、删除表格
- **对齐**：左/中/右
- **图片**：点击上传、拖拽上传、粘贴截图（存储在服务器 `backend/data/uploads/`）
- **表情**：40 个常用 Emoji 快速插入
- **链接 / 分割线**
- **三种编辑模式**：📖 阅读（只读预览）、✏️ 编辑（富文本 WYSIWYG）、`</>` Markdown（源码编辑，切换时自动转换为富文本）
- 当天日记/文档默认编辑模式，非当天默认只读模式
- 粘贴 Markdown 文本自动转换为富文本
- **设置功能**：可自定义默认字体和字号（localStorage 持久化）
- 自动保存（800ms 防抖）

---

## 服务器信息

| 项目 | 信息 |
|------|------|
| 云服务商 | 阿里云 ECS |
| 系统 | Ubuntu 24.04 |
| 开放端口 | 22 (SSH)、80 (HTTP)、443 (HTTPS)、ICMP |
| SSH 登录 | `ssh -i ~/.ssh/xiaoyao.pem root@<服务器IP>` |
| 项目路径 | `/opt/tradingRecords` |
| 进程管理 | systemd (`trading.service`) |

---

## 项目结构

```
program/
├── README.md
├── portal/                          # 门户静态页面
│   ├── index.html                   # 首页（山水风格 + 退出按钮）
│   └── login.html                   # 登录页（密码显隐切换）
│
├── backend/                         # FastAPI 后端
│   ├── requirements.txt             # fastapi, uvicorn, sqlalchemy, pydantic, python-multipart
│   ├── database.py                  # 数据库连接与会话
│   ├── models.py                    # ORM 模型 (Trade, Review, Notebook, Note)
│   ├── schemas.py                   # Pydantic 请求/响应模型
│   ├── auth.py                      # HMAC 签名会话认证
│   ├── main.py                      # 应用入口、中间件、全部 API 路由
│   └── data/                        # 数据目录（自动生成，已 gitignore）
│       ├── trading.db               # SQLite 数据库
│       ├── auth.json                # 认证凭据（用户名 + 密码哈希）
│       ├── .secret                  # 会话签名密钥
│       └── uploads/                 # 上传的图片文件
│
├── frontend/                        # 交易记录前端 (/trading/)
│   ├── package.json
│   ├── vite.config.js               # base: '/trading/', 代理 /api → localhost:8000
│   └── src/
│       ├── App.jsx                  # 路由与布局（含返回首页按钮）
│       ├── api/index.js             # Axios + 401 拦截跳转登录
│       └── pages/                   # Dashboard, TradeList, TradeForm, ReviewList
│
├── frontend-notes/                  # 知识笔记前端 (/notes/)
│   ├── package.json                 # antd, tiptap, lunar-javascript, dayjs...
│   ├── vite.config.js               # base: '/notes/', 代理 /api → localhost:8000
│   └── src/
│       ├── App.jsx                  # 主布局（图标侧栏 + Tab 切换）
│       ├── App.css                  # 全局样式
│       ├── api/index.js             # Axios + 401 拦截跳转登录
│       ├── utils/
│       │   └── weather.js           # 天气 API 封装（Open-Meteo + 地理定位）
│       └── components/
│           ├── IconSidebar.jsx      # 左侧图标导航栏（首页/日记/文档/设置）
│           ├── SettingsModal.jsx   # 编辑器设置弹窗（默认字体/字号）
│           ├── HomePage.jsx         # 首页（公历农历 + 天气 + 统计 + 历史）
│           ├── DiaryView.jsx        # 日记（迷你日历 + 标签 + 日期树 + 编辑器）
│           ├── DocView.jsx          # 文档（嵌套文件夹树 + 编辑器）
│           ├── MiniCalendar.jsx     # 自定义迷你日历组件（中文）
│           └── NoteEditor.jsx       # TipTap 富文本编辑器（字体/字号/颜色/表格/图片上传...）
│
└── deploy/                          # 部署配置
    ├── nginx.conf                   # Nginx 站点配置（Cookie 认证，无 auth_basic）
    ├── trading.service              # systemd 服务定义
    ├── setup.sh                     # 首次部署脚本
    └── update.sh                    # 更新部署脚本（拉取 + 构建 + 重启）
```

---

## 开发流程

### 本地调试

**前置条件**：Node.js 18+、Python 3.10+

```bash
# 1. 安装后端依赖（首次或依赖变更时）
cd program/backend
pip3 install -r requirements.txt

# 2. 安装前端依赖（首次或依赖变更时）
cd program/frontend && npm install
cd program/frontend-notes && npm install
```

**启动本地服务**（开两到三个终端）：

```bash
# 终端 1 — 后端（DEV_MODE=1 跳过认证，--reload 文件修改自动重载）
cd program/backend
DEV_MODE=1 python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# 终端 2 — 交易前端 → http://localhost:5173/trading/
cd program/frontend
npm run dev

# 终端 3 — 笔记前端 → http://localhost:5174/notes/
cd program/frontend-notes
npm run dev
```

> Vite 已配置 `/api` 代理到 `localhost:8000`，前后端联调无需额外配置。
>
> `DEV_MODE=1` 会跳过 Cookie 认证检查，所有 API 直接可用。
>
> 若端口 8000 被占用，执行 `lsof -ti:8000 | xargs kill -9` 释放端口。

### 部署到服务器

```bash
# 1. 本地提交推送
cd program && git add -A && git commit -m "描述" && git push

# 2. 远程一键更新
ssh -i ~/.ssh/xiaoyao.pem root@<服务器IP> "cd /opt/tradingRecords && bash deploy/update.sh"
```

`update.sh` 自动完成：`git pull` → 安装依赖 → 构建两个前端 → 同步 Nginx/门户配置 → 重启服务。

### 首次部署额外步骤

初始化登录账号（在服务器上执行，仅需一次）：

```bash
curl -X POST http://127.0.0.1:8000/api/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"username":"你的用户名","password":"你的密码"}'
```

---

## API 接口

所有接口前缀 `/api`，线上需 Cookie 认证，本地 `DEV_MODE=1` 时免认证。

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/setup` | 初始化账号（仅首次，之后不可调用） |
| POST | `/api/auth/login` | 登录（设置 session_token Cookie） |
| POST | `/api/auth/logout` | 退出（清除 Cookie） |
| GET | `/api/auth/check` | 检查登录状态 |

### 文件上传

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload` | 上传图片（multipart/form-data） |
| GET | `/api/uploads/{filename}` | 获取已上传的图片 |

### 交易记录

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/trades` | 交易列表（分页、多字段筛选） |
| POST | `/api/trades` | 创建交易 |
| GET | `/api/trades/{id}` | 获取单笔 |
| PUT | `/api/trades/{id}` | 更新交易 |
| DELETE | `/api/trades/{id}` | 删除交易 |
| GET | `/api/trades/statistics` | 统计分析（胜率、盈亏、品种/策略/错误分布） |

### 复盘

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/reviews` | 复盘列表 |
| POST | `/api/reviews` | 创建复盘 |
| GET | `/api/reviews/{id}` | 获取单条 |
| PUT | `/api/reviews/{id}` | 更新 |
| DELETE | `/api/reviews/{id}` | 删除 |

### 笔记本（文件夹）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/notebooks` | 列表 |
| POST | `/api/notebooks` | 创建（支持 parent_id 嵌套） |
| PUT | `/api/notebooks/{id}` | 更新 |
| DELETE | `/api/notebooks/{id}` | 删除（级联删除笔记） |

### 笔记

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/notes` | 列表（按类型、笔记本、日期、关键词筛选） |
| POST | `/api/notes` | 创建 |
| GET | `/api/notes/{id}` | 获取单条 |
| PUT | `/api/notes/{id}` | 更新 |
| DELETE | `/api/notes/{id}` | 删除 |
| GET | `/api/notes/stats` | 统计（日记/文档数量、字数、最近文档） |
| GET | `/api/notes/calendar` | 日历数据（某月有日记的日期列表） |
| GET | `/api/notes/diary-tree` | 日记日期树（年 > 月 > 日结构） |
| GET | `/api/notes/history-today` | 历史上的今天（往年同日日记） |

---

## 数据备份

```bash
# 在服务器上执行
cp /opt/tradingRecords/backend/data/trading.db /opt/tradingRecords/backend/data/trading_backup_$(date +%Y%m%d).db

# 备份上传的图片
tar czf /opt/tradingRecords/backend/data/uploads_backup_$(date +%Y%m%d).tar.gz /opt/tradingRecords/backend/data/uploads/
```

---

## 安全策略

- SSH 密钥登录（已禁用密码登录）
- UFW 防火墙：仅开放 22/80/443/ICMP
- 自定义会话认证（HMAC 签名 Cookie，7 天有效期，HttpOnly）
- 前端 401 自动拦截跳转登录页
- 本地开发 `DEV_MODE=1` 环境变量隔离线上认证逻辑
- 图片上传白名单（仅允许 jpg/png/gif/webp/svg/bmp）
