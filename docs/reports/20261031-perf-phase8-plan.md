# 方案:性能套件八期(2026-10-31)

| # | Agent | 增强 | 入口 |
| --- | --- | --- | --- |
| P1 | sql_perf (30) | 新发现 PF007:计划里出现 Exchange SinglePartition(全局排序/汇聚到单分区,典型 ORDER BY 无 LIMIT)判中危,带处方 | `sqlperf` 自动 |
| P2 | slow_query (31) | 报告追加 stage 分解表:各 stage 的 task max/median、溢写、输入量一览(指标里本就带 stages,此前只用于判因不展示) | `slowquery` 自动 |
| P3 | sql_cost (32) | 估算校准:`--calibrate metrics.json`(slowquery 同款指标 JSON)对比 预估 vs 实跑 的扫描量与耗时,给出偏差倍数,供后续人工折算 | `sqlcost --calibrate m.json` |
| P4 | index_advisor (33) | 分桶数按表体量定:带 --stats 时 CLUSTERED BY 的桶数不再固定 32,按 bytes/256MB 取最近 2 的幂(下限 4 上限 512) | `index-adv --stats` 自动 |
| P5 | dag_conflict (35) | 容量缺口一行:按声明起点跑完需要多少 slots/GB(=峰值需求),与现容量的差距直接写进报告头 | `dagconflict` 自动 |
| P6 | 套件级 (30-35) | 一键体检 `perf-report -d DIR`:按约定文件名发现输入(plan.txt/metrics.json+baseline.jsonl/queries/+stats.json/scenario.json/workload/+ddl.sql),能跑的全跑,合并成一份 markdown+JSON;缺的点名跳过 | `seatunnel-agent perf-report -d DIR [-o report.md]` |

## 边界

- P6 只做文件发现与拼装,复用各 agent 的核心与渲染,不新增分析逻辑。
- data_skew 需要 eventlog 大文件,不进 perf-report 的默认扫描(报告里提示)。
- 全部确定性;每条独立 commit。

## 验证

结果与门禁输出见同批结果报告 docs/reports/20261031-perf-phase8.md:

```
python scripts/check_workflow.py --range origin/main...HEAD ->
[PASS] x6(见结果报告)
```
