# AGENTS

本仓库是一个 self-hosted multi-app workspace，不是单一 trading app。当前并列模块包括：
- trading
- notes
- monitor
- ledger
- portal
- backend

## 1. 基本协作约定
- 本地调试统一使用 `./dev.sh`（`up/status/attach/down/restart`）。
- 生产部署统一使用 `deploy/update.sh`。
- 修改前必须先阅读 `docs/MODULE_REGISTRY.md`、`docs/API_STYLE.md`、`docs/BACKEND_STRUCTURE.md`、`docs/DEPENDENCY_POLICY.md`、`docs/SECURITY.md`。
- 涉及部署初始化或 nginx/systemd 的改动，需同步检查 `deploy/setup.sh`、`deploy/nginx.conf` 等相关文件。
- 优化时除功能正确外，需要兼顾易用性、信息密度和整体观感。

## 2. 架构边界
- 不要把业务逻辑写回 `backend/main.py`。
- 不要把新的领域逻辑堆进 `backend/services/runtime.py`。
- Router 负责参数接收、依赖注入和转发；业务逻辑应放在 service。
- 新增 ledger 能力必须优先放在 ledger 域下，不要混入 trading/notes/monitor。
- 不要把 ledger 前端页面塞进 `frontend-trading`；ledger 保持在 `frontend-ledger`。

## 3. 模块改动原则
- 改某个模块时，尽量保持影响范围局部化，避免无关模块连带修改。
- 改 portal、deploy、nginx、dev.sh 这类高影响文件时，必须明确说明改动原因和影响范围。
- 若涉及 API、路由、部署路径、目录结构、模块入口变化，必须同步更新相关文档。

## 4. 文档要求
- 只有在改动影响以下内容时，才需要更新 `README.md` 与 `README.zh-CN.md`：
  - 用户可见功能
  - 路由或入口
  - 部署方式
  - 目录结构骨架
  - 模块说明
  - 运行方式或常用命令
- 若改动仅属于内部重构、实现细节调整、测试补充、样式微调或不影响用户理解的代码整理，通常不需要更新 README。
- 若改动影响验收路径或 smoke 脚本，需同步更新 `docs/` 或 `scripts/` 下相关文件。
- 回复中必须明确说明：
  - README 已更新；或
  - README 无需更新，并说明理由。

## 5. 验证要求
- 后端改动：至少运行相关 `python3 -m pytest -q backend/tests`（或相关子集）。
- 前端改动：至少运行对应前端的 `npm run build`。
- portal / deploy / route 改动：需说明入口、刷新、静态资源路径是否正常。
- 涉及 router/API 注册方式变更时，必须运行：
  - `python3 scripts/check_router_style.py`
  - `bash scripts/check_all.sh`
- 涉及结构、部署、权限、依赖变更时，必须运行相关检查脚本：`scripts/check_deploy.sh`、`scripts/check_naming.sh`、`scripts/check_runtime_size.py`、`scripts/check_all.sh` 中的适用项。
- 若无法完成真实联调，必须明确说明未验证项，不得假装已验证。

## 6. 回复要求
回复应简洁，但必须包含：
- 改动文件路径或范围
- 验证结果
- README 改动文件路径 + 改动摘要；或 README 无需更新的理由
- 仍未完成或未验证的项
