# Agent 74 dup_pipeline — 重复建设检测

日期: 2026-10-31 分支: fresh

## 内容

- `agents/data/dup_pipeline/`：detector（复用 sql_diff 语句形状,新增公共接口 `statement_shapes`）、i18n、report、advisor_llm（可选收敛方案）、api（make_text_router）、tools（MCP）、manifest（group governance, /duppipeline）。
- 检查项：DP001 同源双建——源表集合完全相同,输出表达式重合 ≥50% 记 high（同一张表建了两遍）,仅同源记 medium;DP002 子集派生候选（low）;DP003 源表被 ≥fanout 个目标直读、缺统一中间层（medium）。
- 顺带修复 sql_diff 真 bug：本机 sqlglot 版本 Select 的 FROM 参数键是 `from_` 而非 `from`,导致 FROM 主表从未进入 sources（JOIN 表正常）。已兼容两种键名并补回归测试 `test_from_table_change_detected`。
- CLI `duppipeline`（-f/--text/--fanout/--dialect/--llm/--fail-on-high CI gate）。
- React 页面 `frontend/dup_pipeline/`：SQL 输入 + 扇出阈值 + LLM 复选框,演示预填同源双建案例。
- 测试：`tests/test_dup_pipeline.py` 12 项;`tests/test_duppipeline_page.py` 双页面流;sql_diff 回归后 14 项。
- 示例 `examples/duppipeline_demo/pipelines.sql`。

## 验证

```
tests\test_duppipeline_page.py ..                                        [100%]
============================== 2 passed in 9.05s ==============================

tests/test_dup_pipeline.py + test_sql_diff.py + test_registry.py + test_hub_pages.py
======================= 60 passed, 2 warnings in 13.84s =======================
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
