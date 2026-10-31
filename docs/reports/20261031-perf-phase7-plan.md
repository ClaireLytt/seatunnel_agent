# 方案:性能套件七期(2026-10-31)

六期后每个 agent 单点能力齐了;七期补"跨 agent 闭环"和缺失的
输入/规模形态,仍是确定性核心、CLI 优先、每条独立 commit。

| # | Agent | 增强 | 入口 |
| --- | --- | --- | --- |
| P1 | sql_perf (30) | 统计清单骨架:从计划的扫描明细生成 sqlcost 需要的 stats JSON 模板(表名/列数带好,行数/字节留空待填),打通 计划→成本 的最后一段手工活 | `sqlperf -f plan.txt --stats-template out.json` |
| P2 | slow_query (31) | A/B 对比:两份指标 JSON 直接对比(总量 + 按 stage 对齐的 max/median/溢写差值),定位"哪个 stage 变慢了" | `slowquery --diff a.json b.json` |
| P3 | sql_cost (32) | 批量清单:目录下所有 *.sql 对同一清单各估一次,按核·秒排序出"最贵查询榜"+ 合计行;可按合计扫描挡 CI | `sqlcost -d queries/ -f stats.json [--fail-over-total-scan-gb N]` |
| P4 | index_advisor (33) | 建议 ROI:带 --stats 清单时,对每条分区建议用 sql_cost 估算器重估整个负载,给出"这条建议省多少 GB 扫描",按省量排序 | `index-adv -d workload/ --stats stats.json` |
| P5 | data_skew (34) | 门禁补洞:--fail 目前只看拖尾确认,shuffle 分布确认的肥尾不挡;--shuffle-dist 下确认长尾同样 exit 1 | `skew-runtime log --shuffle-dist --fail` |
| P6 | dag_conflict (35) | 截止时间:DAG 可声明 deadline,时间线报告超期;错峰建议若把受害 DAG 推过 deadline 则明说;可挡 CI | 场景 JSON `"deadline"` + `--fail-on-deadline-miss` |

## 边界

- P4 跨包复用 sql_cost 估算器,不复制实现。
- 全部确定性;页面不动,本批只做 CLI/核心。

## 验证

结果与门禁输出见同批结果报告 docs/reports/20261031-perf-phase7.md:

```
python scripts/check_workflow.py --range origin/main...HEAD ->
[PASS] x6(见结果报告)
```
