# Agent 85 seatunnel_gen — 作业配置生成

日期: 2026-10-31 分支: fresh

## 内容

- `agents/data/seatunnel_gen/`：generator（复用 schema_drift DDL 解析 + config_lint 连接器目录 CONNECTOR_DOCS）、i18n、report、advisor_llm（可选运行前评审）、api（make_text_router）、tools（MCP）、manifest（group build, /seatunnelgen）。
- 生成策略：env（parallelism + job.mode,CDC 源自动 STREAMING,可覆盖）;source/sink 块按连接器目录的必填参数生成——database/table/topic/table_name 形参数按 DDL 表名智能填充并标注"已填充",其余带文档示例值并点名为待替换占位符;plugin_output/plugin_input 自动接线;带点/横线参数名自动加引号。
- 回检守卫：产出经 config_lint.lint_text 零错误后才返回（contract_gen/dq_rulegen 同模式）。
- **顺带修复 config_lint 真 bug**：pyhocon 对带点的引号键保留引号（`'"bootstrap.servers"'`）,linter 比对参数名时不剥引号,导致任何写 `"bootstrap.servers"` 的 Kafka 配置被误报 missing_required + unknown_param。已修复并补回归测试 `test_quoted_dotted_key_matches_documented_param`。
- 定位闭环：config_lint 检查、config_diff 对比、config_migrate 迁移,本 agent **生成**第一份 job.conf——本仓主题最贴的缺口。
- CLI `seatunnelgen`（-f/--text/-s/-k/--job-mode/--parallelism/--conf-out 另存/--llm）。
- React 页面 `frontend/seatunnel_gen/`：DDL + 源/目标连接器 + 模式 + LLM 复选框。
- 测试：`tests/test_seatunnel_gen.py` 13 项（CDC→STREAMING、智能填充 vs 占位符、Kafka topic、config_lint 真回检、多表警告、角色校验 Doris 不能当源）;`tests/test_seatunnelgen_page.py` 双页面流。
- 示例 `examples/seatunnelgen_demo/products.sql`。

## 验证

```
tests\test_seatunnelgen_page.py ..                                       [100%]
============================== 2 passed in 8.49s ==============================

tests/test_seatunnel_gen.py + test_config_lint.py + test_registry.py + test_hub_pages.py
======================= 81 passed, 2 warnings in 15.21s =======================
All checks passed!   (ruff)
```

前端 `npm run lint` 零告警，`npm run build` 成功。

## Gate

```
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```
