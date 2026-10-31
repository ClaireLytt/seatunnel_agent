# 批次结果报告:LLM 开关上 Web(2026-10-31)

## 批准依据

> "think about new functions"（第十七轮：五页补 LLM 勾选框,三入口彻底对齐）

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | 五页各加 opt-in LLM 勾选框;backfillsql 的规格卡片随勾选展开 DDL 输入 | frontend/{dag_optimize,rerun_plan,sync_strategy,pipeline_migrate,backfill_sql} | (本批) |
| 中 | 无 key 503 的页面测试(neutralize_llm fixture,勾选后错误内联显示、无 Traceback) | tests/test_dagopt_page.py | (本批) |
| 低 | 指南新增"LLM 层"章节(能力表 + 确定性/LLM 边界原则) | docs/pipeline_ops_guide.md | (本批) |

## 验证结果

```
pytest -m uitest 五页 + 交接链路 -> 10 passed(含新增 503 用例)
npm run lint/build --workspace 五个页面 -> 全部通过
ruff check tests -> All checks passed!
python scripts/check_workflow.py --range origin/main...HEAD ->
  [PASS] AI 署名: 无 AI 署名(范围 origin/main...HEAD)
  [PASS] 工作区: 工作区干净
  [PASS] 报告落盘: 代码改动已附带落盘报告
  [PASS] 报告含验证输出: 报告含 check_workflow 输出
  [PASS] floor: 无作弊变绿改动(范围 origin/main...HEAD)
  [PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/main...HEAD)
```

## 前后差异

- LLM 能力在 Web/MCP(API)/CLI 三入口完全对齐;默认不勾选,行为零变化。
