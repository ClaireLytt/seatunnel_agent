# 数据工程 Agent 25–29 实施计划

五个新的 data workspace agent，全部沿用平台既有插件模式（`agents/data/<pkg>/manifest.py`
自动发现：hub 卡片 + REST API + MCP/编排器工具），每个 agent 的骨架与 backfill 一致：

```
src/seatunnel_agent/agents/data/<name>/
  __init__.py  manifest.py  <core>.py  report.py  i18n.py  tools.py  api.py
frontend/<name>/            # React 页（external=True），复用 @seatunnel/shared
examples/<name>_demo/       # 演示输入
tests/test_<name>.py        # 确定性核心测试
```

核心全部为确定性分析（字符串进、markdown/JSON 出，不连数据库/调度器），
后期可在每个 agent 上叠加 LLM 增强（分析建议、自然语言摘要等）。

## 25. DAG 依赖优化 — `dag_optimize`（route `/dagopt`，group governance）

输入：任务 DAG（JSON `tasks:[{name,deps,duration?}]` / `edges` / 文本行 `a -> b`）。
分析：
- 传递归约找出冗余串行边（存在更长替代路径的直连边），给出可删依据路径；
- Kahn 分层 → 并行批次、每层宽度、最大并行度；
- 按 duration（缺省 1）算关键路径与理想加速比（总时长/关键路径时长）；
- 单进单出的串行链 → 建议合并；环上节点单独列出。

## 26. 任务重跑规划 — `rerun_plan`（route `/rerun`，group build）

输入：同上格式的 DAG + 失败节点列表（可选：已成功节点、各节点状态）。
分析：最小重跑集合 = 失败节点 + 其下游闭包（排除已成功且无需失效的分支），
按拓扑批次排序输出；同时给出影响面（blast radius）与完全不受影响的分支，
可选命令模板渲染重跑命令。复用 25 的图解析与分层工具。

## 27. 数据回溯与补数 SQL — `backfill_sql`（route `/backfillsql`，group quality）

与现有 backfill（缺口×血缘出"补哪些"）互补：本 agent 负责"怎么补"。
输入：表名、分区列与日期格式、业务日期区间、写入模式
（insert overwrite partition / delete+insert / merge）、方言。
输出：按分区生成幂等、带分区谓词边界的安全补数 SQL，附带前置校验
（行数对比、分区存在性 dry-run）与分批执行顺序。

## 28. 增量同步策略推荐 — `sync_strategy`（route `/syncstrategy`，group build）

输入：每张源表的更新特征清单（行数、日变更率、有无更新时间列/主键、
是否有物理删除、binlog/CDC 可用性、时延要求）。
规则打分 → 推荐 全量 / 时间戳增量 / 主键增量 / CDC，逐表给出理由、
风险与 SeaTunnel 配置要点。

## 29. Pipeline 迁移评估 — `pipeline_migrate`（route `/pipemigrate`，group build）

输入：旧 ETL 脚本目录（SQL/Shell/Python）或任务清单 JSON。
逐任务评估：方言特性与不可直译语法、UDF/外部命令数量、复杂度
（语句数、join 数、控制流）、调度依赖 → 建议目标引擎
（同步类 → SeaTunnel，批处理 SQL → Spark，流式 → Flink）、
工作量分级（S/M/L）与风险清单，汇总迁移顺序建议。

## 实施顺序与里程碑

1. [x] 25 dag_optimize（图解析/分层沉淀为可复用模块）
2. [x] 26 rerun_plan（复用 25 的图工具）
3. [x] 27 backfill_sql
4. [x] 28 sync_strategy
5. [x] 29 pipeline_migrate

每个 agent 独立提交：后端 + 测试 + 示例 + 前端页 + workspace 注册
（frontend/package.json workspaces、npm install、prettier、`seatunnel-agent ui --build` 验证）。

## 二期增强路线（主题：分析结果 → 可执行产物）

按价值排序，逐个实现、独立提交：

1. [x] sync_strategy：按推荐策略生成 SeaTunnel 作业配置骨架（hocon），
   full/incr_timestamp/incr_pk → Jdbc source（带水位 where 模板），
   cdc → MySQL-CDC source；清单可选 update_ts_col/pk_col 字段填充占位符。
2. [x] dag_optimize：有限并发模拟 — 给定 worker 数 k，按批次与时长估算
   makespan，输出 k=1/2/4/8 与无限并发的对比表，量化"并行化值多少"。
3. [x] rerun_plan：时长感知 ETA — DAG 带 duration 时给出每批次与总计的
   预计耗时（批内取最大，批间求和）。
4. [x] backfill_sql：小时级分区网格（date_format 含 HH 时步长改为小时）
   与 grain 字段；按天/小时生成同样幂等的语句块。
5. [x] pipeline_migrate：脚本间表级依赖提取（produced/consumed 表）→
   建议迁移顺序批次（上游任务先迁），并标出跨任务共享表。

## 三期增强路线（输入省力 + 产物再进一步）

1. [x] sync_strategy：直接吃 DDL — 粘贴/指向 CREATE TABLE 脚本，自动识别
   主键与更新时间列生成特征清单，免手写 JSON。
2. [x] dag_optimize：瓶颈敏感度 — 逐个把关键路径任务提速 50% 重算工期，
   指出"优化哪个任务最值"，附每任务 slack。
3. [x] rerun_plan：直接吃调度器状态导出 — {"task":"failed|success"} JSON
   一个输入替代手填 failed/succeeded 两个列表。
4. [x] backfill_sql：后置校验 — 补数后跑的 source×target 逐分区行数
   对账 SQL（FULL OUTER JOIN，只列不一致分区）。
5. [x] pipeline_migrate：对判定为 SeaTunnel 的 sqoop 任务解析
   --connect/--table 直接给出 SeaTunnel 配置骨架。

## Phase 4 roadmap (chain the agents, real-scheduler fit)

1. [x] backfill_sql: explicit "dates" list in the spec (non-contiguous slots)
   + specs_from_plan bridge - feed the backfill planner's plan JSON in,
   get one ready-to-edit spec per impacted table out.
2. [x] dag_optimize: optimized-DAG export - the task JSON with redundant
   edges removed, pasteable back into any DAG tool.
3. [x] rerun_plan: independent recovery groups - connected components of
   the rerun set, so separate failures can be recovered in parallel.
4. [x] sync_strategy: schedule suggestion per latency (streaming / hourly
   cron / daily cron) in the table and the config stub.
5. [x] pipeline_migrate: DataX job JSON support - parse reader/writer,
   assess and emit the SeaTunnel skeleton like sqoop jobs.

## Phase 5 roadmap (fewer, heavier)

1. [x] dag_optimize + rerun_plan: ingest Graphviz DOT (airflow dags show
   output) - shared parse_dag learns digraph syntax.
2. [x] sync_strategy: rows-moved estimate per sync and the saving vs a
   full reload - makes the incremental case quantitative.
3. [x] backfill_sql: overwrite_dynamic mode (Spark dynamic partition
   overwrite) - one statement for the whole range, bounds enforced via
   {start}/{end} placeholders.

## Phase 6 roadmap (capacity-aware)

1. [x] rerun_plan: capacity-aware ETA - makespan of the rerun subgraph
   under 1/2/4 workers, not just the unlimited-parallel batch ETA.
2. [x] pipeline_migrate: export the job-dependency graph with effort as
   duration - feed it to dagopt to answer "how long with k engineers".
3. [x] sync_strategy: fleet summary - daily rows moved by the
   recommended mix vs all-full, one quantified line.
