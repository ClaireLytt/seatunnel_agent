# Agent 78 ddl_evolve — DDL 迁移脚本

日期: 2026-10-31 分支: fresh

## 内容

- `agents/data/ddl_evolve/`：evolver（复用 schema_drift.diff_scripts 差异与 classify_type_change 分级）、i18n、report、advisor_llm（可选上线建议）、api（make_text_router）、tools（MCP）、manifest（group build, /ddlevolve）。
- 生成策略：拓宽型改类型/加列/改名/改注释/新建表（含分区与注释渲染）→ 可直接执行;删表/删列/收窄或不兼容改类型/分区布局变更 → **整条注释掉** + `-- [REVIEW]` 评审提示（归档先行/新列回填/建新表换名）,防误执行。危险步骤排前,脚本可整体粘贴。
- 支持 hive（ADD COLUMNS/CHANGE COLUMN）与 mysql（ADD COLUMN/DROP COLUMN）拼写。
- 闭环定位：schema_drift 报差异,本 agent 出脚本——与 contract_gen（检查→产出）同模式。
- CLI `ddlevolve`（--old/--new/--dialect/--script-out 另存/--llm）。
- React 页面 `frontend/ddl_evolve/`：双 DDL 输入 + 方言 + LLM 复选框,演示预填拓宽+加列+删列案例。
- 测试：`tests/test_ddl_evolve.py` 12 项（危险步骤全注释断言、widening 放行 narrowing 拦截、mysql 拼写、rename→CHANGE COLUMN、脚本另存）;`tests/test_ddlevolve_page.py` 双页面流。
- 示例 `examples/ddlevolve_demo/{old,new}.sql`。

## 验证

```
tests\test_ddlevolve_page.py ..                                          [100%]
============================== 2 passed in 9.01s ==============================

tests/test_ddl_evolve.py + test_schema_drift.py + test_registry.py + test_hub_pages.py
======================= 85 passed, 2 warnings in 14.02s =======================
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
