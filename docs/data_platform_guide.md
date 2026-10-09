# 数据平台能力使用指南

在 Chat BI / 血缘 / 日志 / PII / 漂移等既有底座上拼装的五个平台级能力。
全部遵循项目哲学：**数学与规则确定性，LLM 只负责叙述**。

## 1. 异动根因联动（t2s-rootcause）

归因回答"哪里变了"，根因联动再往下追两跳：

```
归因(维度贡献) → 血缘(口径表的上游链) → 日志(上游表关联的错误簇) → 结论
```

```bash
seatunnel-agent t2s-rootcause --metric gmv \
    --curr-start 2026-03-08 --compare wow \
    --lineage-dir /warehouse/sql --log-dir /var/log/etl
```

- 比率指标自动分解分子/分母并附 factor_split
- 血缘/日志目录可选：缺省时跳过该跳并在报告中说明
- 日志关联是**名称匹配**（错误簇文本提及口径表或上游表名）；
  未配 schema 快照时不做漂移关联（明示边界）

## 2. 资产健康分 + 治理建议（t2s-health）

```bash
seatunnel-agent t2s-health --qlog-dir logs --lineage-dir /warehouse/sql
```

- 打分（低分在前）：热度 40（qlog 查询次数，对数刻度）
  × 文档 40（表注释 + 列注释覆盖率）× 血缘 20（在血缘图中有边）；
  未提供血缘图时降为 50/50，不跨配置比较
- 治理发现：
  - `zombie_table` — 审计期零查询且血缘无下游（需血缘图）
  - `stale_partitioned` — 分区表超 N 天未查询（`--stale-days`，默认 90）→ 建议 TTL/归档
  - `pii_exposure` — 复用 pii_scan 规则命中的敏感列（提示脱敏，不扣分）

## 3. 数据目录检索（t2s-search）

一句话同时搜三类资产，排序与 Chat BI agent 完全一致（纯委托，无独立打分）：

```bash
seatunnel-agent t2s-search "用户收货地址" --top 5
```

- 表：HybridRetriever 融合排序（关键词 × BM25 × 向量）
- 指标：语义层别名/描述匹配
- 取值：值索引命中（需先 `t2s-index-values`；未构建时自动降级）

## 4. 分区 SLA 监控（t2s-sub --table）

订阅第四形态：表最新分区落后 `today - lag` 即推 ⏰ 告警卡片，新鲜则静默。

```bash
seatunnel-agent t2s-sub add --name orders-SLA --cron "30 9 * * *" \
    --table dwd.orders --lag 1 --webhook https://open.feishu.cn/...
```

- 仅支持分区引擎（hive/sparksql）；非日期分区值显式报错
- 卡片含期望分区、实际最新分区、落后天数

## 5. Schema 迁移脚本（schemadiff --emit-ddl）

漂移报告再往前一步——生成可执行的迁移 ALTER：

```bash
seatunnel-agent schemadiff --old ddl_v1/ --new ddl_v2/ \
    --emit-ddl migration.sql
```

- 自动区：加列 / 放宽型类型变更 / 注释与改名（方言化：hive
  `ADD COLUMNS`/`CHANGE`，mysql 系 `ADD`/`MODIFY`/`RENAME COLUMN`）
- MANUAL REVIEW 区（只注释，**永不自动执行**）：DROP 列/表、
  类型收窄、分区结构变更、新表 CREATE
