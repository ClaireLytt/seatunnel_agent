# Agent 69 offboard_plan — 下线方案

日期: 2026-10-31 分支: fresh

## 内容

- `agents/data/offboard_plan/`：planner（复用 quality_trace.build_graph_from_sql + downstream_of）、i18n、report、advisor_llm（可选下线通告）、api（make_text_router）、tools（MCP）、manifest（group governance, /offboardplan）。
- 编排：沿血缘向下游找消费方——有人在读即 **blocked** 并点名先迁移（含血缘距离）;四阶段步骤：公示（时限 T+N 天）→ 冻结（SET TBLPROPERTIES deprecated + 停产出任务模板,读不受影响）→ 归档（CREATE TABLE archive.x_retired AS SELECT + 行数核对 SQL）→ 删除（DROP 整条注释,ddl_evolve 同纪律,归档核验前不放行）。
- 闭环：field_usage 找候选（FU001 无人读的表）→ 本 agent 出分阶段方案。
- CLI `offboardplan`（-f/--text/-t/--grace-days/--archive-db/--llm/--fail-on-blocked CI gate）。
- React 页面 `frontend/offboard_plan/`：SQL + 表名 + 公示期 + LLM 复选框。
- 测试：`tests/test_offboard_plan.py` 9 项（叶子表放行/中间表受阻点名/归档与 deprecated 模板/DROP 全注释/gate 双向）;页面测试 standard_page_tests 工厂 spec。
- 示例 `examples/offboardplan_demo/pipeline.sql`。

## 验证

```
tests\test_offboardplan_page.py ..                                       [100%]
============================== 2 passed in 8.69s ==============================

tests/test_offboard_plan.py + test_quality_trace.py + test_registry.py + test_hub_pages.py
======================= 62 passed, 2 warnings in 14.98s =======================
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
