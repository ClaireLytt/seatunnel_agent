# 批次结果报告:性能套件三期b(2026-10-30)

## 批准依据

> "go on"（沿既定模式继续叠功能）

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | slow_query 慢查询通报草案(LLM,严格可选):诊断 JSON → 可直接粘到值班群的通报;Web 勾选框 / API llm 字段(无 key 503) / CLI --llm 三入口;报告追加"慢查询通报草稿"节 | slow_query/advisor_llm.py、api.py、i18n.py、cli_cmds/perf_ops.py、frontend/slow_query/* | (本批) |

## 验证结果

```
pytest tests/test_slow_query.py tests/test_perf_ops_cli.py -> 13 passed
  (API 打桩 NOTE 进 result+report、默认路径无变化;CLI 打桩 NOTE-CLI)
pytest tests/test_slowquery_page.py -m uitest -> 2 passed(含无 key 503)
pytest tests -q (非 uitest) -> 3818 passed, 1 skipped
ruff / mypy(slow_query + perf_ops) / eslint / prettier / vite build -> 全绿
python scripts/check_workflow.py --range origin/main...HEAD -> [PASS] x6
```

## 前后差异

- LLM 层第七员:性能套件的慢查询归因也能一键出通报,与运维套件
  rerun_plan 的事故通告同款纪律(一次有界调用、测试打桩、默认关)。
