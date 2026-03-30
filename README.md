# 交易记录与复盘系统

一个面向多品种、多金融衍生品场景（期货、加密货币、股票、外汇）的本地交易记录与复盘分析系统。所有数据存储在本地 SQLite 数据库中，通过 Web 界面进行可视化管理。

## 目录

- [系统架构](#系统架构)
- [功能概览](#功能概览)
- [环境要求](#环境要求)
- [安装与启动](#安装与启动)
- [使用指南](#使用指南)
- [数据模型](#数据模型)
- [API 接口](#api-接口)
- [项目结构](#项目结构)
- [数据备份](#数据备份)

---

## 系统架构

```
┌──────────────────────────┐     HTTP/JSON     ┌──────────────────────────┐
│        前端 (5173)        │ ◄──────────────► │       后端 (8000)         │
│  React + Ant Design       │    /api/*         │  FastAPI + SQLAlchemy     │
│  Recharts 可视化           │                  │                          │
└──────────────────────────┘                   └────────┬─────────────────┘
                                                        │
                                                        ▼
                                               ┌────────────────┐
                                               │  SQLite 数据库  │
                                               │  (本地文件存储)  │
                                               └────────────────┘
```


| 层级  | 技术栈                                           | 说明                                    |
| --- | --------------------------------------------- | ------------------------------------- |
| 前端  | React 19 + Vite 8 + Ant Design 6 + Recharts 3 | 中文界面，响应式布局                            |
| 后端  | Python + FastAPI + SQLAlchemy                 | RESTful API，自动生成 Swagger 文档           |
| 数据库 | SQLite                                        | 零配置，数据文件存储于 `backend/data/trading.db` |


---

## 功能概览

### 1. 交易记录（四层记录体系）

基于"可归因、可统计、可复用"的理念，每笔交易记录覆盖四个层次：


| 层次         | 解决的问题       | 核心字段                                     |
| ---------- | ----------- | ---------------------------------------- |
| **成交流水层**  | 发生了什么       | 日期、品种、合约、方向、价格、数量、盈亏、手续费、滑点、持仓时长、交易时段    |
| **交易决策层**  | 为什么做这笔      | 入场逻辑、出场逻辑、策略类型、市场状态、所属周期、止损/目标设定、是否按计划执行 |
| **行为纪律层**  | 亏损是市场还是自身问题 | 是否计划内、追单、扛单、提前止盈、重仓、报复性交易、心理/身体状态        |
| **标签与复盘层** | 如何改进        | 错误标签（13 种预设）、复盘一句话、备注                    |


额外支持**交易前中后**三段式记录：

- **交易前**：机会识别、胜率理由、风险预判
- **交易中**：是否符合预期、是否改变计划
- **交易后**：交易质量评估、根因分析、可复制性判断

### 2. 可视化仪表盘

- **核心指标卡片**：总交易数、胜率、总盈亏、盈亏比、平均盈利/亏损、最大连胜/连亏
- **累计盈亏曲线**：展示账户净值变化趋势
- **品种盈亏分布**：柱状图，快速识别优势/劣势品种
- **策略统计**：各策略的盈亏、交易次数、胜率对比
- **错误标签统计**：横向柱状图，定位最频繁的交易错误
- **日期范围筛选**：支持按时间段分析

### 3. 交易列表管理

- 分页表格，支持按日期、类型、品种、方向、状态筛选
- 列排序（日期、盈亏）
- 行内编辑、删除操作
- 盈亏金额红绿色标识

### 4. 复盘系统（日/周/月三级）


| 复盘类型    | 核心问题                             |
| ------- | -------------------------------- |
| **日复盘** | 最佳/最差交易、是否违纪、执行评分(1-10)、明天避免什么   |
| **周复盘** | 盈利/亏损来源、该继续/减少的交易、重复错误、下周聚焦一个问题  |
| **月复盘** | 能力vs运气、优势策略、利润侵蚀行为、品种池/仓位调整、暂停模式 |


### 5. 多品种支持


| 交易类型 | 特有字段支持                                              |
| ---- | --------------------------------------------------- |
| 期货   | 品种分类(黑色/能化/有色/农产品/股指/国债)、主力/次主力/远月、临近交割月、换月阶段、高波动时段 |
| 加密货币 | 通用字段适配                                              |
| 股票   | 通用字段适配                                              |
| 外汇   | 通用字段适配                                              |


### 6. 错误标签系统

内置 13 种常见交易错误标签，支持多选：

```
无计划开仓 | 追涨杀跌 | 止损不坚决 | 提前止盈 | 盈利单拿不住
亏损单死扛 | 仓位过大 | 频繁交易 | 情绪化交易 | 与策略不符
逆势操作   | 低流动性误判 | 夜盘执行变形
```

---

## 环境要求


| 依赖      | 最低版本 |
| ------- | ---- |
| Python  | 3.9+ |
| Node.js | 18+  |
| npm     | 8+   |


---

## 安装与启动

### 1. 安装后端依赖

```bash
cd program/backend
pip3 install -r requirements.txt
```

### 2. 安装前端依赖

```bash
cd program/frontend
npm install
```

### 3. 启动服务

需要同时启动后端和前端，建议使用两个终端窗口：

**终端 1 — 启动后端（端口 8000）：**

```bash
cd program/backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

**终端 2 — 启动前端（端口 5173）：**

```bash
cd program/frontend
npm run dev
```

### 4. 访问系统


| 地址                                                         | 说明             |
| ---------------------------------------------------------- | -------------- |
| [http://localhost:5173](http://localhost:5173)             | 前端界面           |
| [http://localhost:8000/docs](http://localhost:8000/docs)   | API Swagger 文档 |
| [http://localhost:8000/redoc](http://localhost:8000/redoc) | API ReDoc 文档   |


首次启动时，SQLite 数据库文件 `backend/data/trading.db` 会自动创建。

---

## 使用指南

### 录入交易

1. 点击侧边栏「新建交易」或交易列表页右上角「新建交易」按钮
2. 在「成交流水」Tab 填写必填字段：交易日期、交易类型、品种、方向、开仓时间、开仓价、数量
3. 按需切换其他 Tab 补充决策逻辑、行为纪律、交易前中后记录
4. 在「标签与复盘」Tab 勾选错误标签，写下复盘一句话
5. 点击「保存」

**建议**：先从最小可用版本开始（基本成交信息 + 入场理由 + 是否计划内 + 盈亏 + 复盘一句话），保证能持续记录一个月后再逐步补全其他字段。

### 平仓更新

1. 在交易列表中找到持仓记录，点击编辑
2. 填写平仓价、平仓时间、盈亏金额
3. 将状态改为「已平」
4. 保存

### 查看统计

在仪表盘页面查看所有**已平仓**交易的统计数据。可通过日期范围筛选查看特定时段的表现。

### 创建复盘

1. 点击侧边栏「复盘」
2. 切换 Tab 选择日/周/月复盘类型
3. 点击「新建复盘」
4. 填写对应问题并保存

---

## 数据模型

### Trade 表（交易记录）

```
trades
├── id                    INTEGER   主键
├── created_at            DATETIME  创建时间
├── updated_at            DATETIME  更新时间
│
├── ─── 成交流水层 ───
├── trade_date            DATE      交易日期 (必填)
├── instrument_type       STRING    交易类型: 期货/加密货币/股票/外汇 (必填)
├── symbol                STRING    品种 (必填)
├── contract              STRING    合约代码
├── category              STRING    品种分类
├── direction             STRING    方向: 做多/做空 (必填)
├── open_time             DATETIME  开仓时间 (必填)
├── close_time            DATETIME  平仓时间
├── open_price            FLOAT     开仓价 (必填)
├── close_price           FLOAT     平仓价
├── quantity              FLOAT     数量/手数 (必填)
├── margin                FLOAT     保证金
├── commission            FLOAT     手续费
├── slippage              FLOAT     滑点
├── pnl                   FLOAT     盈亏金额
├── pnl_points            FLOAT     盈亏点数
├── holding_duration      STRING    持仓时长
├── is_overnight          BOOLEAN   是否隔夜
├── trading_session       STRING    交易时段
├── status                STRING    状态: open/closed
│
├── ─── 期货特有 ───
├── is_main_contract      STRING    主力/次主力/远月
├── is_near_delivery      BOOLEAN   临近交割月
├── is_contract_switch    BOOLEAN   换月阶段
├── is_high_volatility    BOOLEAN   高波动时段
├── is_near_data_release  BOOLEAN   重要数据/政策窗口
│
├── ─── 交易决策层 ───
├── entry_logic           TEXT      入场逻辑
├── exit_logic            TEXT      出场逻辑
├── strategy_type         STRING    策略类型
├── market_condition      STRING    市场状态
├── timeframe             STRING    所属周期
├── core_signal           TEXT      核心信号
├── stop_loss_plan        FLOAT     止损设定
├── target_plan           FLOAT     目标位设定
├── followed_plan         BOOLEAN   是否按计划执行
│
├── ─── 行为纪律层 ───
├── is_planned            BOOLEAN   计划内交易
├── is_impulsive          BOOLEAN   临时起意
├── is_chasing            BOOLEAN   追单
├── is_holding_loss       BOOLEAN   扛单
├── is_early_profit       BOOLEAN   提前止盈
├── is_extended_stop      BOOLEAN   扩大止损
├── is_overweight         BOOLEAN   重仓
├── is_revenge            BOOLEAN   报复性交易
├── is_emotional          BOOLEAN   情绪影响
├── mental_state          STRING    心理状态
├── physical_state        STRING    身体状态
│
├── ─── 交易前中后 ───
├── pre_opportunity       TEXT      看到的机会
├── pre_win_reason        TEXT      胜率理由
├── pre_risk              TEXT      风险预判
├── during_match_expectation TEXT   是否符合预期
├── during_plan_changed   TEXT      是否改变计划
├── post_quality          STRING    交易质量评估
├── post_repeat           BOOLEAN   重来还做吗
├── post_root_cause       TEXT      根因分析
├── post_replicable       BOOLEAN   可复制性
│
├── ─── 标签与复盘 ───
├── error_tags            TEXT      错误标签 (JSON数组)
├── review_note           TEXT      复盘一句话
└── notes                 TEXT      备注
```

### Review 表（复盘记录）

```
reviews
├── id                    INTEGER   主键
├── created_at            DATETIME  创建时间
├── updated_at            DATETIME  更新时间
├── review_type           STRING    类型: daily/weekly/monthly (必填)
├── review_date           DATE      复盘日期 (必填)
│
├── ─── 日复盘 ───
├── best_trade            TEXT      最佳交易及原因
├── worst_trade           TEXT      最差交易及原因
├── discipline_violated   BOOLEAN   是否违反纪律
├── loss_acceptable       BOOLEAN   亏损是否可接受
├── execution_score       INTEGER   执行质量评分 (1-10)
├── tomorrow_avoid        TEXT      明天要避免什么
│
├── ─── 周复盘 ───
├── profit_source         TEXT      主要赚钱来源
├── loss_source           TEXT      主要亏损来源
├── continue_trades       TEXT      该继续的交易类型
├── reduce_trades         TEXT      该减少的交易类型
├── repeated_errors       TEXT      重复出现的错误
├── next_focus            TEXT      下周聚焦改善一个问题
│
├── ─── 月复盘 ───
├── profit_from_skill     TEXT      盈利来自能力还是运气
├── best_strategy         TEXT      真正有优势的策略
├── profit_eating_behavior TEXT     吞噬利润的行为
├── adjust_symbols        TEXT      是否调整品种池
├── adjust_position       TEXT      是否调整仓位体系
├── pause_patterns        TEXT      是否暂停某类模式
│
├── ─── 通用 ───
├── summary               TEXT      总结
└── content               TEXT      详细内容
```

---

## API 接口

所有接口前缀为 `/api`，完整的交互式文档访问 `http://localhost:8000/docs`。

### 交易记录


| 方法       | 路径                       | 说明     | 参数                                                                                                          |
| -------- | ------------------------ | ------ | ----------------------------------------------------------------------------------------------------------- |
| `GET`    | `/api/trades`            | 交易列表   | `page`, `size`, `date_from`, `date_to`, `instrument_type`, `symbol`, `direction`, `status`, `strategy_type` |
| `POST`   | `/api/trades`            | 创建交易   | Request Body (JSON)                                                                                         |
| `GET`    | `/api/trades/{id}`       | 获取单笔交易 | 路径参数 `id`                                                                                                   |
| `PUT`    | `/api/trades/{id}`       | 更新交易   | 路径参数 `id` + Request Body                                                                                    |
| `DELETE` | `/api/trades/{id}`       | 删除交易   | 路径参数 `id`                                                                                                   |
| `GET`    | `/api/trades/statistics` | 统计分析   | `date_from`, `date_to`, `instrument_type`, `symbol`                                                         |


### 统计分析返回字段

```json
{
  "total": 100,
  "win_count": 55,
  "loss_count": 45,
  "win_rate": 55.0,
  "total_pnl": 12500.0,
  "avg_pnl": 125.0,
  "max_pnl": 3200.0,
  "min_pnl": -1800.0,
  "avg_win": 450.0,
  "avg_loss": -277.78,
  "profit_loss_ratio": 1.62,
  "max_consecutive_wins": 7,
  "max_consecutive_losses": 4,
  "pnl_by_symbol": [{"symbol": "螺纹钢", "pnl": 5600.0}],
  "pnl_by_strategy": [{"strategy": "趋势突破", "pnl": 8000.0, "count": 30, "win_rate": 60.0}],
  "pnl_over_time": [{"date": "2026-03-01", "daily_pnl": 500.0, "cumulative_pnl": 500.0}],
  "error_tag_counts": [{"tag": "追涨杀跌", "count": 12}]
}
```

### 复盘记录


| 方法       | 路径                  | 说明     | 参数                                                    |
| -------- | ------------------- | ------ | ----------------------------------------------------- |
| `GET`    | `/api/reviews`      | 复盘列表   | `review_type`, `date_from`, `date_to`, `page`, `size` |
| `POST`   | `/api/reviews`      | 创建复盘   | Request Body (JSON)                                   |
| `GET`    | `/api/reviews/{id}` | 获取单条复盘 | 路径参数 `id`                                             |
| `PUT`    | `/api/reviews/{id}` | 更新复盘   | 路径参数 `id` + Request Body                              |
| `DELETE` | `/api/reviews/{id}` | 删除复盘   | 路径参数 `id`                                             |


---

## 项目结构

```
program/
├── README.md
├── backend/
│   ├── requirements.txt          # Python 依赖
│   ├── database.py               # 数据库连接与会话管理
│   ├── models.py                 # SQLAlchemy ORM 模型 (Trade, Review)
│   ├── schemas.py                # Pydantic 请求/响应模型
│   ├── main.py                   # FastAPI 应用入口与路由定义
│   └── data/
│       └── trading.db            # SQLite 数据库文件 (自动生成)
│
└── frontend/
    ├── package.json              # Node.js 依赖与脚本
    ├── vite.config.js            # Vite 配置 (含 API 代理)
    ├── index.html                # HTML 入口
    └── src/
        ├── main.jsx              # React 入口 (ConfigProvider 中文化)
        ├── App.jsx               # 路由与布局 (侧边栏导航)
        ├── App.css               # 全局样式
        ├── api/
        │   └── index.js          # Axios API 封装
        └── pages/
            ├── Dashboard.jsx     # 仪表盘 (统计卡片 + 图表)
            ├── TradeList.jsx     # 交易列表 (表格 + 筛选)
            ├── TradeForm.jsx     # 交易表单 (5 Tab 四层记录)
            └── ReviewList.jsx    # 复盘管理 (日/周/月)
```

---

## 数据备份

数据库为单个文件，备份只需复制：

```bash
cp program/backend/data/trading.db program/backend/data/trading_backup_$(date +%Y%m%d).db
```

恢复时将备份文件重命名为 `trading.db` 替换即可。

---

## 设计理念

本系统遵循"四层记录 + 三级复盘"的方法论：

> 最好的交易记录系统 = **客观流水** + **主观决策** + **行为纪律** + **周期复盘** + **标签统计**

系统设计原则：

1. **渐进式使用**：必填字段仅 7 个（日期、类型、品种、方向、开仓时间、开仓价、数量），其余均为选填，避免记录负担过重导致放弃
2. **可归因分析**：通过错误标签和策略标签，将模糊的"总是亏"转化为"主要亏在第 X 类错误"
3. **过程导向**：区分"好交易亏钱"和"坏交易赚钱"，优化过程质量而非盯单笔结果
4. **本地优先**：所有数据存储在本地，无需联网，保护交易隐私

