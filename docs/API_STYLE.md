# API Style

本文件记录当前 router 风格现状，并定义后续统一目标。

## 当前现状

### Legacy 风格

- `trading` 及多数历史 router 采用 `APIRouter(prefix="/api")`。
- 路由注册主要使用 `router.add_api_route(...)`。
- 代表文件包括：
  - `backend/routers/trading.py`

### 已迁移模块/文件

- `backend/routers/monitor.py` 已迁移为模块级 prefix + decorator 风格，当前使用 `prefix="/api/monitor"`。
- `backend/routers/notes.py` 已迁移为模块级 prefix + decorator 风格，当前使用 `prefix="/api/notes"`。
- `backend/routers/notebook.py` 已迁移为模块级 prefix + decorator 风格，当前使用 `prefix="/api/notebooks"`。
- `backend/routers/todo.py` 已迁移为模块级 prefix + decorator 风格，当前使用 `prefix="/api/todos"`。
- `backend/routers/review.py` 已迁移为模块级 prefix + decorator 风格，当前使用 `prefix="/api/reviews"`。
- `backend/routers/review_sessions.py` 已迁移为模块级 prefix + decorator 风格，当前使用 `prefix="/api/review-sessions"`。
- `backend/routers/trade_plans.py` 已迁移为模块级 prefix + decorator 风格，当前使用 `prefix="/api/trade-plans"`。
- `backend/routers/knowledge.py` 已迁移为模块级 prefix + decorator 风格，当前使用 `prefix="/api/knowledge-items"`。

### Ledger 风格

- `ledger` 采用 `APIRouter(prefix="/api/ledger")`。
- 路由声明主要使用 `@router.get/post/put/delete(...)` decorator。
- 代表文件：`backend/routers/ledger.py`。

## 后续目标风格

- 目标风格是“模块级前缀 + decorator 声明式路由”：
  - router 前缀明确到模块级，例如 `/api/ledger`、未来的 `/api/trading`、`/api/notes`。
  - 路由定义优先使用 `@router.get/post/...`。
  - router 文件只负责参数接收、依赖注入和转发，不承载业务逻辑。
- 不在同一个模块内继续混合两种风格，避免新增漂移。

## 过渡规则

- 历史 router 继续按任务逐步迁移，不做无范围控制的批量重写。
- 对已有 legacy router：
  - 如果只是补小功能且仍在历史 router 中维护，可暂时沿用现有写法。
  - 不允许一边沿用 `prefix="/api"`，一边随意引入新的模块路径约定，导致同模块出现第三种风格。
- 对新域或单独重构的模块：
  - 优先采用“模块级前缀 + decorator”目标风格。
  - 路由路径应先在本文件和 `docs/MODULE_REGISTRY.md` 中登记，再落代码。
