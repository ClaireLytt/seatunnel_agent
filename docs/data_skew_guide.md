# 数据倾斜 Agent 使用指南

面向大数据 SQL（Spark SQL / MaxCompute SQL / Hive SQL）与 SeaTunnel 同步作业的
数据倾斜「检测 → 修改 → 复测」闭环工具。入口：

- **Web UI**：首页 → 数据倾斜（`/dataskew`）
- **CLI**：`seatunnel-agent skew` / `skew-splitkey` / `skew-stats`
- **MCP**：`seatunnel-agent skew-mcp`（独立 server），或统一工具箱 `seatunnel-agent mcp`

## 能力分层

| 层 | 覆盖场景 | 是否需要连库 | 是否需要 LLM |
|---|---|---|---|
| 静态规则（DS001–DS013） | 计算层：SQL 里语法可见的倾斜写法 | 否 | 否 |
| LLM 改写 | 在静态发现的基础上产出优化后 SQL | 否 | 是 |
| 连库探查（probe） | 数据层：热点值 / NULL 占比 / 表行数实测 | 是 | 否 |
| 一致性实测 | 改写前后两版 SQL 的结果对比 | 是 | 否 |
| SeaTunnel 分片键体检 | 同步层：source 并行读的 `partition_column` 分布 | 是 | 否 |

### 静态规则一览

`DS001/002` COUNT(DISTINCT) 单点与多重去重、`DS003` 全局 DISTINCT、
`DS004` UNION 去重、`DS005` 全局 ORDER BY、`DS006` 笛卡尔积/缺 ON、
`DS007` NULL 关联键、`DS008` JOIN 键上套函数、`DS009` 窗口无 PARTITION BY、
`DS010` 动态分区未打散、`DS011` 过多 JOIN、`DS012` JOIN 键含 rand()、
`DS013` 小表广播提示。全部为纯文本扫描——不执行 SQL、不依赖外部解析器，
报告按严重度（高/中/低）分级并附各引擎参数建议。

## Web UI 工作流

1. 粘贴 SQL（或从 SQL Review 页带入），选方言与模式（静态 / LLM 改写）→ 分析。
2. 可选：展开「连接数据源」连库（Hive / Spark SQL / MySQL / PostgreSQL / SQLite），
   点「实测校验」——静态“疑似”会升级为实测“确认/排除”，报告追加：
   - 热点值 Top-N、NULL 占比、行数与判定；
   - 基于实测值的引擎参数与改写模板；
   - 存储/建模层建议（确认热点列不宜作分区/分桶/分片键）。
3. LLM 模式下生成优化 SQL 后，可点「一致性实测」运行两版 SQL 比对行数/聚合值。
4. 历史面板可回载过去的分析（`logs/data_skew.jsonl`，自动轮转）。

### SeaTunnel 分片键体检（UI）

连库后展开「SeaTunnel 分片键体检」，粘贴或上传作业配置（HOCON）：

- 解析 JDBC source 的基表与 `partition_column`（CDC 连接器的
  `database-name(s)` / `table-name(s)` / `scan.incremental.snapshot.chunk.key-column`
  同样识别），在所连数据库上实测该列 NDV / NULL 占比 / top-1 占比；
- 实测数值/日期类候选列并排序，给出可直接粘贴的 source 配置片段；
- **多 source 配置**：逐个体检（单次上限 3 个），共用一节报告；
- 同表的上一次体检会渲染为「复测对比」行——改完键再测一次即看到
  “已解决 / 仍未解决 / 出现退化”；
- 当实测出更优分片键时出现 **「下载修改后配置」** 按钮：下载的就是你粘贴的
  配置文本、仅把分片键改写为推荐列（注释与格式原样保留）。仅单 source
  配置提供写回——多 source 的文本级修改可能改错位置，请按报告手动改。

## CLI

```bash
# 静态扫描（可作 pre-commit / CI 门禁）
seatunnel-agent skew -f job.sql --dialect spark --fail-on high
seatunnel-agent skew -D sql/ -F json -o skew.json

# 加 LLM 改写
seatunnel-agent skew -f job.sql --llm

# 分片键体检：连库实测配置里的 partition_column
seatunnel-agent skew-splitkey job.conf --ds mysql --db host:3306/shop --db-user u --db-password p

# CI 门禁：已配置键实测为 bad/low_ndv/null 时退出码 1
seatunnel-agent skew-splitkey job.conf --ds mysql --fail

# 闭环：把实测推荐键写回配置（原文件备份为 .bak），再体检即见「复测对比：已解决」
seatunnel-agent skew-splitkey job.conf --ds mysql --apply
seatunnel-agent skew-splitkey job.conf --ds mysql

# 历史统计
seatunnel-agent skew-stats -n 50
```

说明：

- `--db` 缺省时读 `.env` 中该 `--ds` 数据源的连接配置；
- `--sample 10` 按 10% 表采样估算（仅 Hive/Spark/PG 生效，其余引擎自动忽略）；
- 多 source 配置可正常体检（逐个出报告），但 `--apply` 会拒绝并提示手动修改。

## MCP 工具

`seatunnel-agent skew-mcp` 暴露（统一工具箱 `seatunnel-agent mcp` 亦包含）：

| 工具 | 说明 |
|---|---|
| `skew_check(sql, dialect?, lang?)` | 静态倾斜扫描，Markdown 报告 |
| `skew_check_file(path, ...)` | 同上，输入为文件路径 |
| `skew_split_key(conf, ds_type?, sample_pct?, lang?)` | 分片键体检（按 `.env` 连库，只读探查） |
| `skew_split_key_file(path, ...)` | 同上，输入为配置文件路径 |
| `skew_split_key_apply(conf, ds_type?, sample_pct?, lang?)` | 在体检基础上返回**写入推荐分片键后的完整配置文本**（不落盘，由调用方保存；仅单 source） |

所有工具错误即文本、永不抛异常；`skew_check` 系列零依赖，`skew_split_key`
系列只发起 COUNT / GROUP BY 只读查询。

## 与数据比对页的联动

- 比对报告的倾斜卡片会定性 A/B 两侧分布：**不一致 → 同步链路病灶**（去查
  分片键），**两侧同倾斜 → 业务事实**（去优化计算层 SQL）；结论随 webhook 推送。
- 「两侧同倾斜」的跳转按钮会带上 B 侧连接信息（3 分钟 cookie，不含密码）落到
  本页并预填连接面板。
- 比对趋势数据携带 `skew_top1` / `skew_gini` 及 `_jump` 漂移字段，告警规则形如
  `skew_top1>50:2`、`skew_top1_jump>10:1`，趋势图含倾斜子图。

## 判定阈值（供解读报告）

- 热点：top-1 占比 ≥ 20% 确认、≥ 5% 疑似；NULL 占比 ≥ 10% 确认；
- 分片键：NDV < 4 × 并行任务数 判 `low_ndv`；`tasks = max(partition_num, env.parallelism, 2)`；
- 体检每列固定两条有界查询（统计 + top-1），候选列最多 5 个、并发最多 4。
