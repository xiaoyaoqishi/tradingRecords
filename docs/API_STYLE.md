# API Style

本文件记录当前 router 风格现状，并定义后续统一目标。

## 当前现状

### Trading 兼容例外

- `backend/routers/trading.py` 已迁移为 decorator 风格，但继续保留 `APIRouter(prefix="/api", tags=["trading"])`。
- 这是正式兼容例外，不是待修复 bug。
- 当前 trading 对外 API 继续使用：
  - `/api/trades`
  - `/api/trade-brokers`
  - `/api/trade-review-taxonomy`
- 禁止在普通重构中新增独立的 trading 模块级 API 前缀。
- 如未来需要新的 trading 模块级 API 前缀，必须单独发起 API v2 迁移，不能在普通重构中顺手修改。

### 已迁移模块/文件

- `backend/routers/trading.py` 已迁移为 decorator 风格，当前仍保留 `prefix="/api"` 以兼容历史 API。
- `backend/routers/monitor.py` 已迁移为模块级 prefix + decorator 风格，当前使用 `prefix="/api/monitor"`。
- `backend/routers/notes.py` 已迁移为模块级 prefix + decorator 风格，当前使用 `prefix="/api/notes"`。
- `backend/routers/notebook.py` 已迁移为模块级 prefix + decorator 风格，当前使用 `prefix="/api/notebooks"`。
- `backend/routers/todo.py` 已迁移为模块级 prefix + decorator 风格，当前使用 `prefix="/api/todos"`。
- `backend/routers/review.py` 已迁移为模块级 prefix + decorator 风格，当前使用 `prefix="/api/reviews"`。
- `backend/routers/review_sessions.py` 已迁移为模块级 prefix + decorator 风格，当前使用 `prefix="/api/review-sessions"`。
- `backend/routers/trade_plans.py` 已迁移为模块级 prefix + decorator 风格，当前使用 `prefix="/api/trade-plans"`。
- `backend/routers/knowledge.py` 已迁移为模块级 prefix + decorator 风格，当前使用 `prefix="/api/knowledge-items"`。

### Legacy Infrastructure Routers

- 以下 infrastructure routers 暂未迁移，当前允许继续保留 `prefix="/api"` 或 `add_api_route(...)`：
  - `backend/routers/auth.py`
  - `backend/routers/admin.py`
  - `backend/routers/audit.py`
  - `backend/routers/health.py`
  - `backend/routers/upload.py`
  - `backend/routers/recycle.py`
  - `backend/routers/poem.py`
- 这些文件后续单独迁移，当前不纳入强制失败范围。

### Ledger 风格

- `ledger` 采用 `APIRouter(prefix="/api/ledger")`。
- 路由声明主要使用 `@router.get/post/put/delete(...)` decorator。
- 代表文件：`backend/routers/ledger.py`。

### Router 检查范围

- `scripts/check_router_style.py` 当前只强制覆盖“已迁移业务 router 集合”：
  - `trading.py`
  - `monitor.py`
  - `notes.py`
  - `notebook.py`
  - `todo.py`
  - `review.py`
  - `review_sessions.py`
  - `trade_plans.py`
  - `knowledge.py`
  - `ledger.py`
- legacy infrastructure routers 只输出 warning，不作为失败条件。

## 后续目标风格

- 目标风格是“模块级前缀 + decorator 声明式路由”：
  - 除 trading 兼容例外外，router 前缀应明确到模块级，例如 `/api/ledger`、`/api/notes`。
  - 路由定义优先使用 `@router.get/post/...`。
  - router 文件只负责参数接收、依赖注入和转发，不承载业务逻辑。
- `trading.py` 属于历史兼容例外：当前仅统一为 decorator 风格，继续保留 `prefix="/api"`。
- 不在同一个模块内继续混合两种风格，避免新增漂移。

## 过渡规则

- 历史 router 继续按任务逐步迁移，不做无范围控制的批量重写。
- 对已有 legacy router：
  - 如果只是补小功能且仍在历史 router 中维护，可暂时沿用现有写法。
  - 不允许一边沿用 `prefix="/api"`，一边随意引入新的模块路径约定，导致同模块出现第三种风格。
- 对新域或单独重构的模块：
  - 优先采用“模块级前缀 + decorator”目标风格。
  - 路由路径应先在本文件和 `docs/MODULE_REGISTRY.md` 中登记，再落代码。
