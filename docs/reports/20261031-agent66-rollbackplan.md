# Agent 66 rollback_plan — 回滚编排

日期: 2026-10-31 分支: fresh

## 内容

- `agents/data/rollback_plan/`：planner（build_graph_from_sql 血缘 + downstream_of 拓扑分层）、i18n、report、advisor_llm（可选 LLM 事故通报）、api（make_text_router）、tools（MCP）、manifest（group build, /rollbackplan）。
- 计划结构：第 0 层恢复坏表（snapshot / rerun / overwrite 三种模板，分区子句渲染）→ 按拓扑层级重跑下游（层内可并行，附调度器 clear+backfill 提示）→ 每张涉及表验证 SQL；给 durations 时估算总时长。
- CLI `rollbackplan`（-f/-t/-p/--mode/--snapshot/--dialect/--llm）。
- React 页面 `frontend/rollback_plan/`：SQL + 坏表 + 坏分区 + 模式 + 快照表输入，演示预填，LLM 复选框。
- 测试：`tests/test_rollback_plan.py` 17 项；`tests/test_rollbackplan_page.py` 双页面流（run + nokey 503）。
- 示例 `examples/rollbackplan_demo/pipeline.sql`。

## 验证

```
tests\test_rollbackplan_page.py ..                                       [100%]
============================== 2 passed in 8.27s ==============================

tests\test_quality_trace.py ..................                           [100%]
============================= 35 passed in 3.89s ==============================
All checks passed!   (ruff)
```

前端 `npm run lint` 零告警，`npm run build` 成功（vite 6, 60 modules）。

## Gate

```
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```
