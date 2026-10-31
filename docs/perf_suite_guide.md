# SQL 性能套件使用指南

围绕「跑前预判 → 跑后归因」的性能工具组（30–35 批次），与管道运维套件
（docs/pipeline_ops_guide.md）互补。全部确定性核心、不连引擎/集群：
粘贴导出物进来，拿结论和处方回去。

| Agent | Web | 一句话 |
|---|---|---|
| 执行计划分析 | `/sqlperf` | 引擎到底计划了什么：join/shuffle/裁剪/下推 |
| 索引分区推荐 | `/indexadvisor` | 查询频次说话：分区、分桶、组合索引该给谁 |
| 资源消耗预测 | `/sqlcost` | 跑之前算量级：扫描/shuffle/内存/耗时 |
| 慢查询根因 | `/slowquery` | 跑完归因：倾斜/暴涨/溢写/GC/排队/小文件 |
| 并发冲突检测 | `/dagconflict` | 多 DAG 同集群：超容窗、写写冲突、错峰 |
| 倾斜长尾（增强） | `skew-runtime --shuffle-dist` | p99 肥尾与热点分区（挂在 data_skew） |

与既有工具的分工：sql_review 读**源码**、data_skew 管**倾斜专项**、
sql_perf 读**引擎计划**、slow_query 读**运行指标** — 四个视角互不重叠，
处方互相指路。

## 跑前三件套

1. **`/sqlperf`** — 粘 `EXPLAIN [FORMATTED]` 输出（Spark/Hive）。
   发现 PF001–PF006：笛卡尔积（高）、PartitionFilters 为空的全分区扫描
   （高）、谓词未下推（中，典型如过滤列套了 cast）、超出 join 所需的
   重复 shuffle（中）、可广播的 SortMergeJoin、≥20 列的宽扫描。
   每条带处方；扫描明细表列出每表的裁剪与下推状态。
2. **`/indexadvisor`** — 查询目录或粘贴多条 SQL，可选建表 DDL。
   sqlglot 统计每表每列的等值/范围/join/group 频次：分区列=时间样式且
   等值最高频，分桶列=最热 join key，组合索引=等值按频次+范围列收尾。
   附命中语句数与 DDL 片段；解析不了的语句列出不乱猜。
3. **`/sqlcost`** — SQL × 表统计（rows/bytes/partitions/partition_col/
   columns）。扫描按分区与列裁剪打折，join 两侧交换（≤10MB 自动广播），
   聚合再交换一次；输出内存峰值、核·秒、建议并行度下 0.5x–2x 耗时区间。
   假设全部随报告列出，清单缺的表点名排除。

## 跑后归因

4. **`/slowquery`** — 执行指标 JSON（duration、scan/shuffle 字节、GC/
   排队、各 stage 的 task max/median 与溢写）± 历史基线 jsonl。
   根因 SQ001–SQ006 按占比排序：倾斜（→data_skew）、扫描暴涨对比基线
   （→sqlperf）、溢写（→sqlcost）、GC、排队（→dagconflict）、小文件。
   标题给出相对基线中位数的回归倍数。
5. **`skew-runtime <eventlog> --shuffle-dist`** — 在既有拖尾诊断之外看
   p99 长尾：几个热点分区的模式 max/median 可能不夸张但 p99 很肥；
   表格给出 p50/p99/倾斜比/热点任务，处方是换高基数键或对热点加盐。

## 并发推演

6. **`/dagconflict`** — 场景 JSON：集群容量 + 各 DAG 的任务（deps/
   duration/slots/memory_gb/writes）与启动偏移。按依赖 ASAP 推演时间线：
   超容时间窗与窗内任务、跨 DAG 写同表的写写冲突；错峰建议先重新模拟
   再给出（顺延哪个 DAG 多久、峰值降到多少、剩几个窗）。

## 典型闭环

- 夜里慢了：`/slowquery` 定位主因 → 倾斜去 data_skew / 计划问题去
  `/sqlperf` / 容量问题去 `/sqlcost` 重定容 / 排队去 `/dagconflict` 错峰。
- 新表上线：`/indexadvisor` 按历史查询定分区分桶 → `/sqlcost` 预估大
  查询的量级 → 上线后用 `/sqlperf` 验证裁剪真的生效。

示例输入在 `examples/`：`sqlperf_demo`、`indexadvisor_demo`、
`sqlcost_demo`、`slowquery_demo`、`dagconflict_demo`、
`dataskew_demo/eventlog_shuffle_dist.jsonl`，各页预填即点即用。

## CLI 入口

五个页面都有同名命令行入口，`-F json` 可进流水线：

```bash
seatunnel-agent sqlperf -f plan.txt                  # 加 --llm --sql-file q.sql 出改写草案
seatunnel-agent sqlperf -f plan.txt --fail-on-severity high  # 有 high 发现就 exit 1
seatunnel-agent index-adv -d workload/ --ddl ddl.sql
seatunnel-agent sqlcost --sql-file q.sql -f stats.json \
  --fail-over-scan-gb 50 --fail-over-shuffle-gb 20   # 超预算 exit 1，可做 CI 闸门
seatunnel-agent slowquery -f metrics.json --baseline runs.jsonl \
  --history slow_ledger.jsonl --llm                  # 台账 + LLM 通报草稿（可选）
seatunnel-agent dagconflict -f scenario.json \
  --fail-on-conflict --history capacity.jsonl        # 有冲突 exit 1;峰值记台账
```

预算闸门的可复制 workflow 在
`examples/ci/github-actions-sqlcost-budget.yml`：PR 改到的每条查询
按表统计清单估算，超预算直接挡在上线前。
