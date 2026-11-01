# 批次结果报告:性能套件三期c(2026-10-30)

## 批准依据

> "think about new functions"（gate 家族补齐到性能套件剩余两员）

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | sqlperf --fail-on-severity high|medium:EXPLAIN 出现该级别及以上发现(笛卡尔积/裁剪丢失等)时逐条打印 FINDING 行并 exit 1 | cli_cmds/perf_ops.py | (本批) |
| 中 | dagconflict --fail-on-conflict:存在超容窗或写写冲突 exit 1;--history 容量台账(峰值 slots/内存/窗口数/冲突数,峰值回升黄字) | cli_cmds/perf_ops.py | (本批) |

## 验证结果

```
pytest tests/test_perf_ops_cli.py -> 9 passed
  (demo 计划 high 发现挡/干净计划过;demo 场景冲突挡且台账照记)
pytest tests -q (非 uitest) -> 3820 passed, 1 skipped
ruff / mypy(perf_ops) -> 全绿
python scripts/check_workflow.py --range origin/main...HEAD -> [PASS] x6
```

## 前后差异

- gate 家族:dagopt 回归 / sync-strategy 风险 / sqlcost 预算之外,新增
  计划级别闸门与并发冲突闸门;history 家族新增容量台账(trends 可直接汇总)。
