# 批次结果报告:性能套件三期d(2026-10-30)

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | sqlcost --assume-partition 表:列[:分区数](可多次):按假设分区克隆统计重估一遍,报告追加 what-if 节(扫描前后 GB 与省比);没省时明说原因(SQL 未对该列等值过滤);规格错/分区数未知为用法错误不瞎猜 | cli_cmds/perf_ops.py | (本批) |

## 验证结果

```
pytest tests/test_perf_ops_cli.py -> 10 passed
  (users 按 join 键假设分区后省比 >0;坏规格与缺分区数 exit 2)
pytest tests -q (非 uitest) -> 3821 passed, 1 skipped
ruff / mypy(perf_ops) -> 全绿
python scripts/check_workflow.py --range origin/main...HEAD -> [PASS] x6
```

## 前后差异

- index_advisor 的分区建议从"建议"变成"能省 X%"的数字:DDL 没跑之前
  就能用 sqlcost 验证值不值得做。
