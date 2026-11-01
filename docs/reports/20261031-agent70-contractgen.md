# Agent 70 contract_gen — 契约草稿生成

日期: 2026-10-31 分支: fresh

## 内容

- `agents/data/contract_gen/`：generator（schema_drift 解析器复用,DDL → 契约草稿）、i18n、report、advisor_llm（可选收紧建议）、api（make_text_router）、tools（MCP）、manifest（group governance, /contractgen）。
- 承诺策略：只承诺表当前已做到的——列与类型（可关）、分区布局、注释纪律（覆盖率达标 require_comments,否则逐列钉住已有注释）；分区列同列清单一并声明,保证草稿对同一 DDL 回检零发现;生成前经 contract_check.parse_contract 回检,产出即可消费。
- CLI `contractgen`（-f/--text/-t 限表/--no-types/--threshold/--strict/--dialect/--llm）。
- React 页面 `frontend/contract_gen/`：DDL 输入、限表、固定类型/冻结结构/LLM 复选框,演示预填混合覆盖率两张表。
- 测试：`tests/test_contract_gen.py` 16 项（含 contract_check 真回检零发现）；`tests/test_contractgen_page.py` 双页面流。
- 示例 `examples/contractgen_demo/tables.sql`（三张全注释 + 一张 25% 覆盖）。

## 验证

```
tests\test_contractgen_page.py ..                                        [100%]
============================== 2 passed in 8.19s ==============================

tests\test_contract_gen.py + test_contract_check.py
============================= 41 passed in 3.90s ==============================

tests/test_registry.py tests/test_hub_pages.py
======================= 35 passed, 2 warnings in 12.67s =======================
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
