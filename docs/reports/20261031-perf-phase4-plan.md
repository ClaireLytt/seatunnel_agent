# 方案:性能套件四期(2026-10-31)

针对 30–35 六个 agent 各补一个闭环缺口,全部确定性核心、不连引擎,
沿用既定节奏:核心函数 → CLI → 测试 → 单独 commit。

| # | Agent | 增强 | 入口 |
| --- | --- | --- | --- |
| P1 | sql_perf (30) | 计划前后对比:优化前/后两份 EXPLAIN,报告已解决/新增/遗留发现与每表裁剪变化 | `sqlperf -f new.txt --before old.txt` |
| P2 | slow_query (31) | 基线晋升:本次 run 回归低于阈值时追加进基线 jsonl,基线自动滚动 | `slowquery --promote-baseline [--promote-under N]` |
| P3 | sql_cost (32) | 改写省比:原 SQL 与改写 SQL 同清单各估一次,输出扫描/shuffle/内存/耗时差值 | `sqlcost --compare-sql-file q2.sql` |
| P4 | index_advisor (33) | 现状审计:解析 DDL 里已有 PARTITIONED BY / CLUSTERED BY,对照负载指出分区列无人过滤、最热 join key 未分桶、建议缺口 | `index-adv --ddl ddl.sql`(自动附审计节) |
| P5 | data_skew (34) | 加盐 what-if:对 shuffle 分布热点按 N 路打散重算 p99/倾斜比,未给 N 时找达标最小 N | `skew-runtime --shuffle-dist --what-if-salt [N]` |
| P6 | dag_conflict (35) | 新 DAG 准入:对指定 DAG 在时间轴上扫描候选起点,选冲突窗最少、峰值最低的错峰位 | `dagconflict --place DAG` |

## 边界

- 不动 web 页结构;P1/P3 的 API 字段若一行可加则顺带,否则只做 CLI。
- 每条增强独立提交,pytest + ruff + check_workflow 全绿后进下一条。
- 示例输入补进 examples/ 对应 demo 目录。
