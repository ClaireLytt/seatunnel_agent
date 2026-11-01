# Agent 71 sql_diff — SQL 语义对比

日期: 2026-10-31 分支: fresh

## 内容

- `agents/data/sql_diff/`：differ（sqlglot 血缘栈复用,两版脚本按写入目标配对）、i18n、report、advisor_llm（可选 MR 评审）、api（make_text_router）、tools（MCP）、manifest（group build, /sqldiff）。
- 分级：删语句/删输出列/INSERT INTO↔OVERWRITE 翻转=破坏;列表达式/WHERE/GROUP BY·HAVING 变更、源表进出=风险;新增语句或列=提示。纯格式化、别名、顺序变化不计入（canonical SQL 比较）;SELECT * 出警告（列级变化不可见）;裸 SELECT 按位置配对。
- CLI `sqldiff`（--old/--new/--dialect/--llm/--fail-on-breaking CI gate）。
- React 页面 `frontend/sql_diff/`：双 SQL 文本框 + LLM 复选框,演示预填口径变更案例。
- 测试：`tests/test_sql_diff.py` 13 项;`tests/test_sqldiff_page.py` 双页面流。
- 示例 `examples/sqldiff_demo/{old,new}.sql`。

## 验证

```
tests\test_sqldiff_page.py ..                                            [100%]
============================== 2 passed in 8.03s ==============================

tests/test_sql_diff.py + test_registry.py + test_hub_pages.py
======================= 48 passed, 2 warnings in 13.14s =======================
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
