# 方案:性能套件九期(2026-10-31)

| # | Agent | 增强 | 入口 |
| --- | --- | --- | --- |
| P1 | sql_perf (30) | 计划台账:`--history ledger.jsonl` 记每次分析的高/中/提示发现数与 shuffle 数,接夜间 trends(套件里唯一没台账的页) | `sqlperf --history f.jsonl` |
| P2 | slow_query (31) | 处方落地:报告尾部按根因生成"下一步命令"块——SQ001→data_skew、SQ002→sqlperf、SQ003→sqlcost、SQ005→dagconflict 的可复制 CLI 模板(确定性字符串,不猜路径,占位符标注) | `slowquery` 自动 |
| P3 | sql_cost (32) | 并行度 what-if:`--parallelism N` 用指定并行度替代自动推荐重算耗时区间,和自动值并排 | `sqlcost --parallelism 64` |
| P4 | index_advisor (33) | 冷列报告:带 --ddl 时列出 DDL 声明但负载从未引用的列(按表),宽表裁剪/归档的直接依据 | `index-adv --ddl` 自动附 |
| P5 | data_skew (34) | 分布台账:`--dist-history f.jsonl` 记最差 p99/p50 倾斜比与热点 stage 数,看倾斜是否在恶化 | `skew-runtime --shuffle-dist --dist-history f.jsonl` |
| P6 | dag_conflict (35) | 错峰编排器:`--compact` 对全部 DAG 贪心重排起点(按峰值占用降序,逐个放到最早无冲突位),输出建议起点表与 前后峰值/冲突/完工时间 对比,每步重新模拟验证 | `dagconflict --compact` |

## 边界

- P2 的命令模板只引用本次调用已知的文件路径,未知输入一律 `<...>` 占位。
- P6 是建议输出,不改输入文件;deadline 声明照常校验。
- 全部确定性;每条独立 commit;10-30 架构评审的 4 项候选不混入本批。

## 验证

结果与门禁输出见同批结果报告 docs/reports/20261031-perf-phase9.md:

```
python scripts/check_workflow.py --range origin/main...HEAD ->
[PASS] x6(见结果报告)
```
