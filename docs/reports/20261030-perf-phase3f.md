# 批次结果报告:性能套件三期f(2026-10-30)

## 批准依据

> "go on"（沿既定模式继续叠功能）

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | what-if 三入口对齐:API 加 assume_partitions 字段(坏规格 400 不瞎猜),/sqlcost 页加可选「What-if 假设分区」输入(空格/逗号分隔多条);规格解析下沉 estimator.parse_assumptions,CLI/API 共用 | sql_cost/estimator.py、api.py、frontend/sql_cost/*、cli_cmds/perf_ops.py | (本批) |

## 验证结果

```
pytest tests/test_sql_cost.py tests/test_perf_ops_cli.py -> 18 passed
  (API what-if 省比>0 且报告含 What-if 节;nope 与缺分区数均 400)
pytest tests/test_sqlcost_page.py -m uitest -> 1 passed
pytest tests -q (非 uitest) -> 3823 passed, 1 skipped
ruff / mypy(sql_cost + perf_ops) / eslint / prettier / vite build -> 全绿
python scripts/check_workflow.py --range origin/main...HEAD -> [PASS] x6
```

## 前后差异

- what-if 此前 CLI 独有,现 Web/API/CLI 三入口一致;与 /indexadvisor
  的交接按钮连成完整故事:建议 → 递 SQL → 填统计 → 假设分区看省比。
