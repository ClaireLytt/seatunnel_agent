# Agent 86 dag_gen — 调度文件生成

日期: 2026-10-31 分支: fresh

## 内容

- `agents/data/dag_gen/`：generator（复用 sql_diff.statement_shapes）、i18n、report、advisor_llm（可选部署前评审）、api（make_text_router）、tools（MCP）、manifest（group build, /daggen）。
- 定位收窄说明：原计划"SQL → dag_check 可消费的依赖清单",实现前核对发现 dag_check 本身就从 SQL 建图并出批次/关键路径——按去重纪律改为"检查→产出"闭环：dag_check 诊断图,本 agent **出可部署的调度文件**。
- 生成策略：每个写入目标一个 BashOperator（`<RUN table>` 占位命令,task_id 由表名清洗去重）;目标互读自动 `>>` 依赖边;脚本外上游表在对应任务上方注释点名该挂 sensor 的位置并汇总清单;dag_id 标识符校验、cron 可配。
- 回检守卫：产出经 `ast.parse` 零错误才返回（contract_gen/dq_rulegen/seatunnel_gen 同模式）。
- CLI `daggen`（-f/--text/--dag-id/--schedule/--dialect/--py-out 另存/--llm）。
- React 页面 `frontend/dag_gen/`：SQL + dag_id + cron + LLM 复选框。
- 测试：`tests/test_dag_gen.py` 11 项（任务/边/外部上游、ast.parse、边接线、task_id 清洗去重、py 另存后可解析）;`tests/test_daggen_page.py` 用 **standard_page_tests 工厂**写成 30 行 spec（工厂上线后第一个新 agent,验证复利成立）。
- 示例 `examples/daggen_demo/pipeline.sql`。

## 验证

```
tests\test_daggen_page.py ..                                             [100%]
============================== 2 passed in 8.73s ==============================

tests/test_dag_gen.py + test_sql_diff.py + test_registry.py + test_hub_pages.py
======================= 60 passed, 2 warnings in 14.71s =======================
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
