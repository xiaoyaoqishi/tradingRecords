# Ledger Smoke Checklist

## 1. 前置条件
- 已启动本地服务：`./dev.sh up`
- 可正常登录系统账号（至少一个可写数据账号）
- `frontend-ledger` 已完成构建验证：`cd frontend-ledger && npm run build`
- 若验证生产配置，服务器已执行 `deploy/update.sh`

## 2. 手工验收步骤
1. 打开门户首页 `/`，确认存在“账务管理”入口卡片。
2. 点击“账务管理”进入 `/ledger/`，应自动落到 `/ledger/dashboard`。
3. 打开账户页 `/ledger/accounts`，新建一个账户（如“现金钱包”）。
4. 打开分类页 `/ledger/categories`，新建一个支出分类（如“餐饮”）。
5. 打开流水页 `/ledger/transactions`，新增一条 `income` 流水。
6. 新增一条 `expense` 流水（绑定上一步分类）。
7. 再新增一条 `transfer` 流水（转出账户与对方账户不同）。
8. 回到 `/ledger/dashboard`，确认汇总卡片和最近流水发生变化。
9. 跳回 `/ledger/transactions`，按 `transaction_type=transfer` 筛选，应有结果。
10. 编辑任一流水并保存，列表应保持当前筛选状态。
11. 删除一条流水，删除后列表刷新且该条目消失。
12. 打开 `/ledger/import`，上传一份 CSV，完成“预览导入”并“确认导入”。
13. 导入完成后跳转到流水页，筛选 `source=import_csv` 可看到新导入记录。
14. 打开 `/ledger/rules`，新建一条规则（如 `merchant_contains=coffee`，动作设置支出分类）。
15. 在 `/ledger/import` 导入一条命中该规则的记录，预览页需显示命中规则摘要。
16. 提交后到 `/ledger/transactions`，确认分类已自动补全。
17. 返回门户 `/`，再次点击“账务管理”，页面应正常打开。

## 3. 期望结果
- 所有页面可访问且刷新不 404（重点验证 `/ledger/dashboard`）。
- 新增/编辑/删除流水可成功落库并反映在 Dashboard。
- 交易筛选可稳定返回结果，URL 参数刷新后可保留关键筛选。
- CSV 导入支持字段映射、预览状态（有效/重复/无效）与提交统计反馈。
- 未登录访问 `/ledger/*` 会跳转 `/login`，登录后可回到原目标页。

## 4. 常见失败排查
- 访问 `/ledger/*` 404：检查 `deploy/nginx.conf` 是否包含 `location /ledger/` 及 `try_files ... /ledger/index.html`。
- 门户无“账务管理”卡片：检查 `portal/index.html` 是否已同步到部署目录 `/opt/tradingRecords/portal/index.html`。
- portal 点击 `/ledger/` 无法打开：检查 `frontend-ledger` 是否已构建并存在 `frontend-ledger/dist`。
- 本地 portal 代理不通：检查 `portal/dev_server.py` 是否配置了 `/ledger/` 上游，默认端口 `5176`。
- 登录后未回跳：检查 URL 是否带 `redirect=/ledger/...`，并确认登录成功返回 200。
- Dashboard 页面加载但图表区空白：确认有支出类流水且分类未被删除。
- CSV 导入后没有记录：检查映射是否覆盖 `occurred_at/amount/transaction_type/account_name` 等关键字段。
- 审计上报报错：`/api/audit/track` 失败不会阻断页面，属于可容忍降级。
