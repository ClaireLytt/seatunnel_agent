# 数据工程 Agent 30–35 实施计划

延续 25–29 的平台插件模式（manifest 自动发现：hub 卡片 + REST + MCP 工具 +
React 页 + CLI），每个 agent 的骨架与质量基线不变：确定性核心、zh/en 报告、
示例、单测 + 页面回归、gate 全 PASS。复用 25–29 沉淀的公共设施
（api_guard.read_whitelisted_file、check_runner 的 emit/gate/history、
advisor_llm 模式、sessionStorage 交接、extra_routers 双页测试）。

## 查重结论（先于开发）

- **34 数据倾斜诊断 → 不新建**。现有 `data_skew` 已覆盖：静态规则
  DS001–DS013、LLM 改写、连库热点实测、SeaTunnel 分片键体检、Spark
  runtime 拖尾诊断。缺口仅剩"Shuffle 分布异常的事件级检测"，作为
  data_skew 的增强项排在本批末尾，不另开 agent。
- **30 与 sql_review/data_skew 分工**：sql_review 管源码级静态规则，
  data_skew 管倾斜专项；30 只做两者都没有的 **EXPLAIN/执行计划分析**
  （粘贴计划文本，不粘 SQL 源码也能诊断）。

## 30. SQL 性能优化（执行计划分析）— `sql_perf`（route `/sqlperf`，group quality）

输入：EXPLAIN / EXPLAIN FORMATTED 的计划文本（Hive/Spark）±原 SQL。
确定性解析计划树：
- Join 链：join 类型（SortMerge/Broadcast/ShuffleHash）、顺序、是否小表
  未广播；
- Shuffle：Exchange 节点数量与位置、重复 shuffle；
- 分区裁剪：PartitionFilters 是否为空、全表扫描的表；
- 扫描：每表 scan 的 pushed filters / 列裁剪情况。
输出 findings（高/中/低）+ 优化后 SQL 要点；可选 LLM 产出改写 SQL。

## 33. SQL 索引与分区推荐 — `index_advisor`（route `/indexadvisor`，group governance）

输入：查询集合（SQL 目录/粘贴多条）× 表 DDL。
统计每表的过滤/关联/聚合列频次（等值、范围、join key、group by），
规则推荐：分区列（高频等值+低基数+时间列优先）、分桶列（高频 join key）、
索引（MySQL/Doris 场景的组合索引顺序）；给出每条推荐命中的查询数与
DDL 片段。复用 sql_review 的语句切分与 lineage 列提取。

## 32. SQL 资源消耗预测 — `sql_cost`（route `/sqlcost`，group quality）

输入：SQL × 表统计清单（行数/字节/分区数，JSON/CSV，复用 sync_strategy
的清单风格）。
自底向上估算：scan 量（分区裁剪折扣）→ join/聚合的行数放大/收缩系数 →
shuffle 字节 → 内存峰值与核时估算区间 + 执行时间量级（给假设清单，
不装精确）。输出"代价卡"：扫描 X GB、shuffle Y GB、建议并行度。

## 31. 慢查询根因分析 — `slow_query`（route `/slowquery`，group quality）

输入：单次执行日志/Spark stage 指标（JSON 或文本）× 可选历史耗时基线
（jsonl，复用 trends 格式）。
规则定位主因并排序：倾斜（max/median task 比）、扫描暴涨（对比基线）、
shuffle 溢写、GC 占比、排队等待、小文件（task 数 vs 数据量）。
输出根因卡 + 对应处方（指向 skew/sqlperf 的具体能力）。

## 35. 并发任务冲突检测 — `dag_conflict`（route `/dagconflict`，group build）

输入：多个 DAG（复用 dag_optimize 解析器，任务带 duration 与资源声明
slots/memory）± 各 DAG 启动时刻。
时间线模拟并发执行：资源峰值超限的时间窗、争抢最严重的任务对、
跨 DAG 写同一张表的写写冲突（复用 pipeline_migrate 的 produces 提取）。
输出冲突清单 + 错峰建议（建议的启动偏移）。

## 34.（增强，非新 agent）data_skew：Shuffle 分布异常检测

输入 Spark shuffle read/write 的按分区字节分布（event log 已有通道），
输出分布倾斜度（p99/median）、热点 partition 清单 — 挂在现有 runtime
诊断面板下。

## 实施顺序与里程碑

1. [x] 30 sql_perf（计划解析器是后续 31/32 的地基）
2. [x] 33 index_advisor（复用 sql_review 列提取）
3. [x] 32 sql_cost（复用 30 的计划/SQL 结构 + 33 的清单解析）
4. [x] 31 slow_query（处方指向 30/34 的能力）
5. [x] 35 dag_conflict（复用 dag_optimize/pipeline_migrate）
6. [x] 34 data_skew shuffle 分布增强

每个 agent 独立提交：后端 + 测试 + 示例 + 前端页 + 页面回归 + 报告落盘；
后期允许在每个 agent 上继续叠加功能（沿 25–29 的 phase 模式）。
