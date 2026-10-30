# 批次结果报告:Agent 31 慢查询根因(2026-10-31)

## 批准依据

> 30-35 批次计划第 4 步

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | slow_query:执行指标 JSON(+可选历史基线 jsonl)→ 规则 SQ001-006 按占比排序:倾斜(max/median≥5x,占比=拖尾超额/总耗时)、扫描暴涨(≥2x 基线中位数)、溢写、GC≥20%、排队≥30%、小文件(<8MB/task 且任务多);每条带证据与指向兄弟 agent 的处方;基线回归倍数进标题 | agents/data/slow_query/ | (本批) |
| 高 | 三入口:/slowquery 页(指标+基线双输入,demo 预填)+ MCP 工具 + REST;示例、6 个单测、1 个页面回归 | frontend/slow_query, tests | (本批) |

## 验证结果

```
pytest tests/test_slow_query.py -> 6 passed
  (demo:SQ001 占比 63% 居首、SQ002 2.1x、SQ003 命中而 GC/排队静默;
   回归 4.19x;GC/排队/小文件三规则;干净运行零命中;坏输入三路径)
pytest -m uitest tests/test_slowquery_page.py -> 1 passed
pytest tests -q -> 3802 passed, 1 skipped
ruff / mypy(slow_query 7 files) -> 全绿
npm run lint/build --workspace slow_query -> 通过
python scripts/check_workflow.py --range origin/main...HEAD -> [PASS] x6
```

## 前后差异

- "为什么慢"从翻日志变成一张排序根因卡;处方闭环:倾斜→data_skew、
  扫描→sql_perf、溢写→sql_cost、排队→dag_conflict(下一个 agent)。
