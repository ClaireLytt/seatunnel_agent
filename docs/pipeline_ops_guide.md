# 数据管道运维 Agent 套件使用指南

围绕「调度优化 → 故障重跑 → 历史补数 → 同步选型 → 迁移评估」五个日常运维场景的
确定性工具套件。全部不连数据库、不连调度器——粘贴导出物进来，拿可执行产物回去。

| Agent | Web | CLI | 一句话 |
|---|---|---|---|
| DAG 依赖优化 | `/dagopt` | `seatunnel-agent dagopt` | 调度在哪儿浪费时间、怎么并行化 |
| 任务重跑规划 | `/rerun` | `seatunnel-agent rerun` | 失败后最少要重跑哪些、按什么顺序 |
| 回溯补数 SQL | `/backfillsql` | `seatunnel-agent backfill-sql` | 历史数据怎么补才安全幂等 |
| 增量同步策略 | `/syncstrategy` | `seatunnel-agent sync-strategy` | 全量、增量还是 CDC，理由与风险 |
| Pipeline 迁移评估 | `/pipemigrate` | `seatunnel-agent pipe-migrate` | 旧 ETL 迁到 SeaTunnel/Spark/Flink 的代价 |

CLI 通用参数：`-f/--text` 输入、`--lang zh|en`、`-F markdown|json`（json 供
CI/脚本消费）、`-o` 落盘。`backfill-sql --plan '<计划JSON>'` 直接出规格骨架；
`dagopt/pipe-migrate --history FILE` 做趋势监测（关键路径蠕变 / 迁移燃尽）；`dagopt --base old.json --fail-on-regression [--tolerance X]` 可作 CI gate——关键路径回归或引入新冗余即 exit 1；`sync-strategy --fail-on-risk latency_without_cdc` 让清单仓库在 CI 挡住满足不了的时延声明（两者的可抄流水线见 examples/ci/github-actions-{dag-regression,sync-inventory}.yml）；`sync-strategy --emit-configs DIR` 与 `pipe-migrate --emit-stubs DIR` 把
SeaTunnel 配置骨架逐个写成 .conf 文件；补数规格加 `"runner":
"spark-sql|beeline|hive|mysql"` 会多出一段失败即停的 bash 执行脚本。

每个 agent 同时是 MCP/编排器工具（`dag_optimize` / `rerun_plan` / `backfill_sql` /
`backfill_specs` / `sync_strategy` / `pipeline_migrate`），统一入口
`seatunnel-agent mcp`，聊天编排页可按关键词路由。

## DAG 依赖优化（/dagopt）

输入三选一：JSON `tasks:[{name,deps,duration?}]`、Graphviz DOT
（`airflow dags show` 的输出直接粘）、或每行一条 `a -> b`。输出：

- 冗余串行边（传递归约），每条附"已由哪条路径保证"，并导出删完冗余边的
  DAG JSON 可直接粘回；
- Kahn 并行批次与最大并行度；按 duration 的关键路径与理想加速比；
- 并发数 1/2/4/8/∞ 的 makespan 对比——并行化值多少一眼可见；
- 瓶颈敏感度：逐个把关键任务提速一半重算工期，优化哪个任务最值排在最前；
- 可选 SLA 时长：三态判定（已满足 / 可达并给出最小提速集合 / 不可达需重构）；
- 单进单出串行链——可合并为一个任务。

## 任务重跑规划（/rerun）

输入同上格式的 DAG + 失败任务名；或直接粘调度器状态导出
（`{"task":"state"}` JSON 或 `task=state` 行，failed/error/up_for_retry
自动归类）。输出：

- 最小重跑集合 = 失败任务 + 下游闭包；上游产出保留、兄弟分支不动；
- 拓扑批次 + 影响面百分比 + 按 duration 的每批次/总计 ETA，
  以及执行槽位 1/2/4 受限时的恢复总时长；
- 闭包内曾成功的任务标记"上游数据失效"仍需重跑；
- 互不相连的失败各成一组，可并行恢复；
- 命令模板 `{task}` 渲染重跑命令，并附批内并行、批间等待、
  失败即停的 bash 执行脚本。

## 回溯补数 SQL（/backfillsql）

输入 JSON 规格：目标表、分区列、业务日期（`start/end` 区间或显式 `dates`
列表）、带 `{date}` 占位符的 source SELECT、写入模式与方言。安全规则硬性
约束：无分区占位符的全表读取直接拒绝；天级封顶 366 天、小时级封顶 31 天。

- 模式：`overwrite`（hive/spark）、`delete_insert`、`merge`（需 keys）、
  `overwrite_dynamic`（spark/hive 动态分区整段一条语句，要求
  `{start}`/`{end}` 占位符）；
- `date_format` 含 `HH` 自动按小时出语句；
- 自带前置行数校验与补数后的逐分区对账 SQL（只列不一致分区）；
- **与补数计划器串联**：把 `/backfill` 页的计划 JSON 粘进"从补数计划生成
  规格"卡片（或 MCP 工具 `backfill_specs`），逐表得到带准确日期的规格骨架，
  填好 source 即可生成最终 SQL。

## 增量同步策略（/syncstrategy）

输入三选一：JSON 特征清单、带表头的 CSV、或直接粘 `CREATE TABLE` DDL
（自动识别主键与 updated_at/update_time/gmt_modified 等更新时间列）。
规则优先级：分钟级时延 + binlog → CDC；有物理删除无 CDC → 全量；
小表/高变更率 → 全量；有更新时间列 → 时间戳增量；仅主键追加表 → 主键增量。

输出逐表：策略 + 规则依据 + 剩余风险（漏删、晚到更新、无主键重复等）+
调度建议（常驻流 / cron）+ 每次同步行数估算与"比全量省 x%"+
可直接填用的 SeaTunnel 作业配置骨架（CDC 用 MySQL-CDC streaming 源，
增量用带水位 where 的 Jdbc query，真实列名来自清单/DDL）。

## Pipeline 迁移评估（/pipemigrate）

输入旧脚本目录（递归扫 `.sql/.hql/.sh/.py` 与 DataX 作业 `.json`）或粘单个
脚本。逐任务输出：

- 目标引擎：纯搬运（sqoop/datax）→ SeaTunnel、批 SQL → Spark SQL、
  流式（kafka/canal）→ Flink、纯编排 shell → 留在调度器；
- S/M/L 工作量：语句数、join、控制流、风险项的透明打分，任务按从易到难排；
- 风险清单：UDF/TRANSFORM、存储过程、Oracle `(+)`、运行时拼接 SQL、
  本地文件读写等无法机械翻译的语法；
- 脚本间表级依赖 → 迁移波次（生产者先迁）与跨任务共享表；
- sqoop/DataX 任务直接给出 SeaTunnel Jdbc→HdfsFile 配置骨架
  （url/表/路径从脚本解析，填凭据即可用）。

## LLM 层（可选，需配置 API key）

五个 agent 各有一个 opt-in 的 LLM 能力，页面勾选框 / API `llm: true` /
CLI `--llm` 三处等价；均为单次有界调用，无 key 返回标准 503：

| Agent | LLM 产出 |
|---|---|
| dagopt | 按收益排序的优化行动清单（引用分析数字） |
| rerun | 可直接贴运维群的事故通告草稿 |
| backfillsql | 按上游 DDL 填充规格的 source 列（`{date}` 边界由确定性代码守住，LLM 丢占位符即弃用） |
| syncstrategy | 落地推进方案：选型解读、切换步骤、监控点、回退 |
| pipemigrate | 风险最大任务（≤3 个）的目标引擎改写建议与代码草案 |

原则：事实、数字与安全规则永远来自确定性层；LLM 只生成需要人审阅的
文本，报告中对应段落均标注"LLM 生成 — 审阅后使用"。

## 典型工作流

1. **断更恢复**：`/freshness` 发现断更 → `/backfill` 算出补哪些表哪些日期 →
   点报告上方「用此计划生成补数 SQL 规格」一键带到 `/backfillsql`（自动出
   逐表规格骨架）→ 填 source 生成幂等 SQL → 跑完用对账 SQL 验收。
2. **调度提速**：`airflow dags show` 的 DOT 粘到 `/dagopt` → 删冗余边的
   DAG 粘回调度器 → 按瓶颈敏感度表优先优化收益最大的任务。
3. **夜间批量失败**：调度器状态导出粘到 `/rerun` → 按独立分组并行恢复，
   每组按批次顺序执行渲染好的命令。
4. **存量迁移立项**：旧脚本目录丢给 `/pipemigrate` → 用 S/M/L 分布和迁移
   波次排期，纯搬运任务拿骨架当天切 SeaTunnel；点「把迁移 DAG 带到依赖
   优化页估工期」一键到 `/dagopt`，makespan 表直接回答"k 个人并行迁移
   要多久"。

示例输入都在 `examples/`：`dagopt_demo/`、`rerun_demo/`、`backfillsql_demo/`、
`syncstrategy_demo/`、`pipemigrate_demo/`，各页默认预填即可直接点按钮体验。
