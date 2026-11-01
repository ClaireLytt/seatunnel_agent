# 方案:性能套件五期(2026-10-31)

四期给 30–35 各补了一个分析能力;五期把它们接进无人值守链路:
每个新能力配上 CI 闸门或可直接套用的处方片段,沿用既定节奏
(核心 → CLI → 测试 → 单独 commit)。

| # | Agent | 增强 | 入口 |
| --- | --- | --- | --- |
| P1 | sql_perf (30) | 对比闸门:优化后计划若引入新发现则 exit 1,防"优化反而更糟"合入 | `sqlperf --before old.txt --fail-on-new` |
| P2 | slow_query (31) | 慢化趋势:台账最近 N 条 duration 持续上涨时在报告点名,可挡 CI | `slowquery --history ledger.jsonl --trend 5 [--fail-on-trend]` |
| P3 | sql_cost (32) | 省比闸门:改写在任一维度反而更贵时 exit 1,护住"改写必须不劣化" | `sqlcost --compare-sql-file q2.sql --fail-if-worse` |
| P4 | index_advisor (33) | 审计闸门:现状审计有发现(IA001–IA004)时 exit 1 | `index-adv --ddl ddl.sql --fail-on-audit` |
| P5 | data_skew (34) | 加盐处方片段:what-if 表下附按盐值生成的改写 SQL 模板(打散侧+膨胀侧) | `--what-if-salt` 自动附带 |
| P6 | dag_conflict (35) | 准入闸门:声明起点劣于最优起点时 exit 1,逼着新 DAG 用错峰位上线 | `dagconflict --place DAG --fail-if-misplaced` |

## 边界

- 只加旗标与渲染,不动既有默认行为;全部确定性。
- 每条独立提交,pytest + ruff + mypy + check_workflow 全绿后进下一条。

## 验证

结果与门禁输出见同批结果报告 docs/reports/20261031-perf-phase5.md:

```
python scripts/check_workflow.py --range origin/main...HEAD ->
[PASS] x6(见结果报告)
```
