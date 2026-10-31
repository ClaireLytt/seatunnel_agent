# Agent 76 field_usage — 字段使用率盘点

日期: 2026-10-31 分支: fresh

## 内容

- `agents/data/field_usage/`：analyzer（复用 schema_drift DDL 解析 + sqlglot 负载解析）、i18n、report、advisor_llm（可选处置建议）、api（make_text_router）、tools（MCP）、manifest（group governance, /fieldusage）。
- 统计：DDL 列 × 查询负载,逐 SELECT 解析别名归属,SELECT/WHERE/JOIN/GROUP BY 引用计数;无限定列只在无歧义（单一来源表含该列）时归属,否则计入 unresolved,从不猜测。
- 分级：FU001 负载从未读过的表（medium,下线候选）;FU002 表被读但列从未被引用（low,裁剪候选;有 SELECT * 的表不出此项——列级统计失明）;FU003 SELECT * 次数（low,盲区）。最热列 TOP10、最冷表在前。
- 边界：asset_value 管表级价值评分,本 agent 下钻到列级;产出直接喂后续 69 offboard_plan。
- CLI `fieldusage`（--ddl/-q/--dialect/--llm/--fail-on-unused CI gate,点名无人读的表）。
- React 页面 `frontend/field_usage/`：双输入（DDL + 负载）+ LLM 复选框。
- 测试：`tests/test_field_usage.py` 9 项（计数/分级/别名归属与歧义跳过/星号盲区豁免/排序/gate）;页面测试用 standard_page_tests 工厂 30 行 spec。
- 示例 `examples/fieldusage_demo/{tables,queries}.sql`。

## 验证

```
tests\test_fieldusage_page.py ..                                         [100%]
============================== 2 passed in 8.55s ==============================

tests/test_field_usage.py + test_registry.py + test_hub_pages.py
======================= 44 passed, 2 warnings in 14.42s =======================
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
