# 批次结果报告:性能套件三期h(2026-10-30)

## 批准依据

> "think about new functions"（沿既定模式叠功能）

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | slowquery -d DIR 批量 triage:目录下所有 *.json 对同一基线逐个诊断,按回归倍数排序出表(run/耗时/回归/主因);--fail-over-regression 以最差 run 挡;批量下 --llm/--history 明确拒绝 | cli_cmds/perf_ops.py | (本批) |

## 验证结果

```
pytest tests/test_perf_ops_cli.py -> 12 passed
  (heavy 1800s 排第一;最差 run 触发 gate;--llm 组合 exit 2)
pytest tests -q (非 uitest) -> 3824 passed, 1 skipped
ruff / mypy(perf_ops) -> 全绿
python scripts/check_workflow.py --range origin/main...HEAD -> [PASS] x6
```

## 前后差异

- 夜间 triage 从逐个 run 变一条命令:一晚指标全量排序,
  直接接 --fail-over-regression 做告警。
