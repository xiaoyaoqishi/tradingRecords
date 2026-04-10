# Trade Source Metadata Normalization (Additive Design Note)

## Why this note

`Trade.notes` 仍是历史主路径，但来源语义已逐步显式化。目标是在不改变粘贴导入与统计口径的前提下，把 source/broker 从“隐式字符串”演进到“显式元数据”。

## Current baseline (kept compatible)

Backend:
- `/api/trades/import-paste` 仍按旧行为写入 notes 标记：
  - `来源券商: ...`
  - `来源: 日结单粘贴导入`
- `source_keyword` 在以下接口保持兼容过滤语义：
  - `/api/trades`
  - `/api/trades/count`
  - `/api/trades/statistics`
  - `/api/trades/positions`
- `/api/trades/sources` 合并三路来源：
  - `trade_brokers`
  - `trade_source_metadata`
  - legacy notes 解析（`来源券商:` / `来源:`）

Frontend:
- 粘贴导入入口与交互保持不变。
- 旧记录（仅 notes、无 metadata）仍可正常浏览和筛选。

## Additive model

- `TradeSourceMetadata`（Trade 1:1）字段：
  - `broker_name`
  - `source_label`
  - `import_channel`
  - `source_note_snapshot`
  - `parser_version`
  - `derived_from_notes`

## Canonical Source Of Truth

- source/broker 在 active code path 的 canonical 字段为 `TradeSourceMetadata`：
  - `broker_name`
  - `source_label`
  - `import_channel`
  - `parser_version`
- `Trade.notes` 中的 `来源券商/来源` 仅作为兼容回退，不再作为主模型。

Compatibility-only fields (阶段性保留):
- `Trade.notes` 中来源标记
- `Trade.review_note`

Future removal candidates（需后续明确迁移窗口）:
1. UI 中直接从 notes 解析来源并作为主展示
2. 把 review 语义继续写在 `review_note` 的主工作流

## Dual-write logic added in this sprint

Backend (`backend/main.py`):
- 粘贴导入 open 行入库后，新增 metadata upsert（双写）。
- 平仓匹配流程中，对受影响记录也执行 metadata upsert（含整手匹配与拆分场景）。
- 以上均不改 notes 内容与 import 接口返回结构。

Read path:
- 读取 source 时保持“metadata + notes fallback”并行兼容。
- metadata 存在时可优先提供显式值；缺失时回退解析 notes。

## Frontend integration in this sprint

Changed files:
- `frontend/src/api/index.js`
  - 新增 `tradeSourceApi.get/upsert`
- `frontend/src/pages/TradeList.jsx`
  - 交易工作台改造（列表+右侧详情抽屉）
  - 抽屉内可编辑：
    - 来源元数据（TradeSourceMetadata）
    - 结构化复盘（TradeReview）
    - legacy notes/review_note（兼容字段）
- `frontend/src/pages/TradeForm.jsx`
  - 完整编辑页新增来源元数据字段加载/保存
  - 旧字段与旧流程保持可用

## Deferred (intentionally)

- 不拆分 paste import 内部流水线
- 不迁移 analytics 定义与计算口径
- 不移除 notes 兼容路径
- 不触碰交易子系统外模块

## Related Sprint Notes

- Analytics + localization sprint文档见：
  - `docs/trading-analytics-localization.md`

## Next safe step

1. 为 metadata 字段补充更细粒度校验与审计字段（仍保持可选与兼容）。
2. 在不改统计口径前提下，逐步减少前端对 notes 文本解析的展示依赖。
3. 等历史覆盖率稳定后，再讨论“metadata-first”更强约束迁移。
