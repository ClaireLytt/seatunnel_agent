# Agent 67 model_review — 建模体检

日期: 2026-10-31 分支: fresh

## 内容

- `agents/data/model_review/`：reviewer（schema_drift 解析器复用,前缀定角色后体检星型结构）、i18n、report、advisor_llm（可选改造建议）、api（make_text_router）、tools（MCP）、manifest（group governance, /modelreview）。
- 边界：metadata_quality 管声明规范（注释/命名/类型反模式）,layer_check 管血缘分层,本 agent 管星型结构本身。
- 检查项：MR001 维表缺主键列（high）;MR002 事实表未分区、MR003 描述性属性混入事实表、MR004 属性跨事实表复制、MR006 宽表超阈值、MR007 事实表无 *_id 外键（medium）;MR005 汇总表无度量列（low）。ods/stg/tmp 原始层豁免（只做宽表检查）。
- CLI `modelreview`（-f/--text/--wide-limit/--dialect/--llm/--fail-on-high CI gate）。
- React 页面 `frontend/model_review/`：DDL 输入 + 宽表阈值 + LLM 复选框,演示预填埋 5 类问题的 4 张表。
- 测试：`tests/test_model_review.py` 12 项;`tests/test_modelreview_page.py` 双页面流。
- 示例 `examples/modelreview_demo/warehouse.sql`。

## 验证

```
tests\test_modelreview_page.py ..                                        [100%]
============================== 2 passed in 8.21s ==============================

tests/test_model_review.py + test_registry.py + test_hub_pages.py
======================= 47 passed, 2 warnings in 13.15s =======================
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
