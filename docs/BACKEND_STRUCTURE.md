# Backend Structure

本文件用于限制后端结构继续漂移，尤其是 `backend/services/runtime.py` 的职责边界。

## runtime.py 的允许职责

`backend/services/runtime.py` 当前只允许承担以下职责：

- `init_runtime()` 等运行期初始化入口。
- 历史兼容迁移入口，例如补列、兼容旧表、兼容旧鉴权数据。
- 仍未拆出的历史导出函数，在重构完成前作为兼容层保留。

## runtime.py 的禁止事项

- 禁止把新的业务逻辑继续堆进 `backend/services/runtime.py`。
- 禁止在其中新增新的领域规则、复杂查询拼装、写入流程或模块专属 service。
- 禁止把本应进入 router / domain service / dedicated service 的逻辑，再次回灌到 `runtime.py`。
- `monitor` 运行期逻辑已迁出到 `backend/services/monitor_runtime.py`，后续新的 monitor 采样、巡检、系统信息聚合与 monitor 站点管理逻辑不得写回 `runtime.py`。
- `notes / notebook / todo` 运行期逻辑已迁出到 `backend/services/notes_runtime.py`，后续新的 notes 域查询、笔记链接索引、默认 notebook 初始化、回收站处理与 todo 逻辑不得写回 `runtime.py`。
- `auth` 运行期逻辑已迁出到 `backend/services/auth_runtime.py`，后续新的认证、登录、登出、setup、鉴权检查与用户权限归一化逻辑不得写回 `runtime.py`。
- `admin` 运行期逻辑已迁出到 `backend/services/admin_runtime.py`，后续新的用户管理、模块权限配置与管理员操作逻辑不得写回 `runtime.py`。
- `audit` 运行期逻辑已迁出到 `backend/services/audit_runtime.py`，后续新的审计写入、审计查询与审计删除逻辑不得写回 `runtime.py`。
- `recycle` 运行期逻辑已迁出到 `backend/services/recycle_runtime.py`，后续新的 recycle / soft delete / restore / purge 逻辑不得写回 `runtime.py`。

## 新逻辑落点

- `trading` 新业务逻辑进入 `backend/trading/` 下对应 service。
- `ledger` 新业务逻辑进入 `backend/services/ledger/` 下对应 service。
- `notes`、`monitor`、`auth`、`admin`、`audit`、`recycle` 等后续新增逻辑，应进入各自 dedicated runtime / service，不应新增到 `runtime.py`。
- router 仅负责参数、依赖和转发，不承载业务实现。

## 历史债务说明

- `runtime.py` 当前上限已下调为 `1592` 行，并继续以 `scripts/check_runtime_size.py` 强制守护。
- 其中同时存在初始化、兼容迁移和历史业务代码，这种混合状态需要后续单独拆分。
- auth/admin/audit 运行期逻辑已迁出；后续拆分应单独发起，不要在业务需求顺手继续扩大该文件。
- review / review_session 运行期逻辑已迁出到 `backend/services/review_runtime.py`，后续新的 review 展示转换、review_session CRUD、trade link 同步与 create-from-selection 逻辑不得写回 `runtime.py`。
- trade_plan 运行期逻辑已迁出到 `backend/services/trade_plan_runtime.py`，后续新的 plan CRUD、trade link / review-session link 同步与 follow-up review session 逻辑不得写回 `runtime.py`。
- knowledge 运行期逻辑已迁出到 `backend/services/knowledge_runtime.py`，后续新的 knowledge item CRUD、category 管理、tag/related note 聚合逻辑不得写回 `runtime.py`。
- poem / upload 小模块运行期逻辑已迁出到 `backend/services/utility_runtime.py`；health 逻辑当前仍在 `backend/routers/health.py` 内联，本轮无需迁出。
