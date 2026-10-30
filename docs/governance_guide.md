# 数据治理三件套使用指南 (Hygiene · Metadata Quality · PII)

一条确定性的治理工作流：**盘点 → 规范 → 保护 → 度量 → 门禁**。
三个 agent 全部不连接数据库、不执行任何语句、不需要 LLM 或 API key，
输入只是你的 SQL/DDL 脚本目录。

| 环节 | Agent | 回答的问题 | 入口 |
|---|---|---|---|
| 盘点 | 数仓卫生 `hygiene` | 哪些可以退役 | `/hygiene` · CLI · REST · MCP `warehouse_hygiene` |
| 规范 | 元数据质量 `metaquality` | 表建得规不规范 | `/metaquality` · CLI · REST · MCP `metadata_quality` |
| 保护 | 敏感数据 `pii` | 敏感列在哪、怎么处置 | `/pii` · CLI · REST · MCP `pii_scan`/`pii_mask` |
| 度量 | `hygiene-stats` / `metaquality-stats` / `impact-stats` | 治理有没有变好 | CLI |

编排器均可自然语言直达：「哪些表可以下线」「检查注释覆盖率」
「这段 SQL 帮我脱敏」。

## 盘点：数仓卫生

```bash
seatunnel-agent hygiene --dir warehouse_sql/
seatunnel-agent hygiene --dir warehouse_sql/ --exempt exempt.yaml --fail-on orphans
```

- **孤儿产出**：只写不读的表（`ads_*` 终端集市天然豁免）
- **死列**：表有人读、列却从未被下游 SELECT（分区列豁免）
- **悬空定义**：有 DDL、不在任何血缘里

外部 BI 直读的表对 SQL 血缘不可见，用豁免清单消掉误报：

```yaml
# exempt.yaml
tables:
  - dw.bi_*
  - ads_legacy.report_2023
```

## 规范：元数据质量

```bash
seatunnel-agent metaquality --dir warehouse_sql/ --fail-on high
```

- 注释覆盖率（逐表百分比 + 缺注释列）
- 跨层命名错配（`dwd` 库里的 `ods_` 表；无前缀属风格、不报）
- 类型反模式：金额列用 FLOAT/DOUBLE（high，丢分——用 DECIMAL）、
  金额列用 STRING（medium，运算隐式转换）、
  非分区日期列用裸 STRING（medium）
- 事实表无分区：`dwd`/`dws` 层的表没有 PARTITIONED BY（medium；
  dim/ods/ads 不报——小维表与服务表合法无分区）

## 承诺：数据契约

```bash
seatunnel-agent contract --dir warehouse_sql/ -c contract.yaml --fail-on high
```

metaquality 查通用规约,contract 查**项目自己的约定**——YAML 里声明
对表的承诺,逐条对照实际 DDL:

```yaml
# contract.yaml
tables:
  - name: dwd.orders
    columns:
      - { name: order_id, type: bigint }        # 类型违约 = high
      - { name: amount, type: decimal, comment: true }
    partitioned_by: [dt]                         # 分区违约 = medium
    require_comments: true                       # 缺注释 = low
    allow_extra_columns: false                   # 契约外列 = low
```

表/列缺失与类型违约 high,分区违约 medium,注释与契约外列 low。
Web 页在 `/contract`,聊天/MCP 工具名 `contract_check`。

## 保护：敏感数据

详见 [pii_guide.md](pii_guide.md)。要点：扫描（命名规则×血缘）→
`--mask` 生成脱敏视图 → 覆盖回验让 `--fail-on` 只拦未处置的高危。

## 收口：权限面

```bash
seatunnel-agent grants --dir warehouse_sql/ --fail-on high
```

解析 GRANT/REVOKE 并净面(同键 REVOKE 抵销),分级报出:
对 PUBLIC 的授权(high)、对同脚本 PII 命中表的授权(high,与
pii_scan 联动)、ALL 宽权限(medium)、库级宽范围(medium)。
Web 页在 `/grants`,聊天/MCP 工具名 `grant_scan`。

## 度量：趋势

每次 CLI/REST 运行自动落档 `logs/*.jsonl`：

```bash
seatunnel-agent hygiene-stats       # 孤儿表 12 → 8（最近 N 次）
seatunnel-agent metaquality-stats   # 注释覆盖 71% → 83%
```

## 门禁：一条流水线串三关

```yaml
- name: Warehouse governance gates
  run: |
    seatunnel-agent hygiene     --dir sql/ --exempt ci/exempt.yaml --fail-on orphans
    seatunnel-agent metaquality --dir sql/ --fail-on high
    seatunnel-agent pii         --dir sql/ --mask --fail-on high
```

三条全部确定性、秒级、零 token——放在 PR 流水线里不心疼。

## 边界

- 一切判定基于静态 SQL/血缘：外部读、调度器视角、真实数据分布不可见。
  报告定位是**线索**而非判决；豁免清单与人工复核是设计的一部分。

---

# Data Governance Trio (English)

A deterministic governance workflow over your SQL/DDL scripts — no
database, nothing executed, no LLM:

1. **Inventory** — `hygiene`: write-only tables (final `ads_*` marts
   exempt), dead columns of read tables, dangling DDL; externally-read
   tables are silenced via a YAML exemption list (`--exempt`).
2. **Conventions** — `metaquality`: comment coverage, cross-layer naming
   mismatches, money-on-float / date-as-bare-STRING anti-patterns.
3. **Protection** — `pii`: scan by naming rules × lineage, generate
   masked-view DDL with `--mask`, and gate CI only on UNCOVERED findings.
4. **Measurement** — every run lands in `logs/*.jsonl`;
   `hygiene-stats` / `metaquality-stats` show the trend.
5. **Gates** — chain the three `--fail-on` commands in one CI step
   (deterministic, seconds, zero tokens).

All three are orchestrator-routable in natural language and exposed as
MCP tools (`warehouse_hygiene`, `metadata_quality`, `pii_scan`/`pii_mask`).
