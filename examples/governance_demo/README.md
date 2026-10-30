# governance_demo — one directory feeds every governance agent

A sample warehouse with every kind of planted trouble, so each governance agent
has something to say: PII columns and their downstream spread, money on DOUBLE,
dates as bare STRING, missing comments and owners, an `ods_` table living in
`dwd`, an unpartitioned `dws` aggregate, an orphan table, a dangling definition
(warehouse.sql); a PUBLIC database grant, ALL PRIVILEGES, a sensitive-table
grant and a GRANT/REVOKE netting pair (grants.sql); drops, a truncate, a
VARCHAR narrowing and a table rename for the migration guard (migration.sql);
and a contract the DDL violates on purpose (contract.yaml). The commands below
run them all; `tests/test_governance_demo.py` pins the planted issues so they
cannot rot.

---

# governance_demo — 一个目录喂饱六个治理 agent

带全套病灶的仓库样例,每个治理 agent 在这里都有话可说:

| 文件 | 植入的病灶 |
| --- | --- |
| warehouse.sql | PII 手机号列及其下游扩散;金额用 DOUBLE;日期裸 STRING;缺注释;dwd 里的 ods_ 表;dws 无分区;dwd/dws 无 owner;孤儿表 dead_end;悬空定义 dim_ghost |
| grants.sql | 对 PUBLIC 的库级授权;ALL PRIVILEGES;敏感表(fact_orders 含手机号)授权;一对 GRANT/REVOKE 净面演示 |
| migration.sql | 删表/删列/清空/STRING→VARCHAR(64) 收窄/表重命名(回滚脚本可从 warehouse.sql 的 CREATE 还原类型) |
| contract.yaml | 对 fact_orders / agg_daily 的承诺,现状刻意违约(类型/缺列/分区) |

```bash
seatunnel-agent pii         -d examples/governance_demo --mask
seatunnel-agent hygiene     -d examples/governance_demo --fail-on orphans
seatunnel-agent metaquality -d examples/governance_demo --fail-on high
seatunnel-agent contract    -d examples/governance_demo -c examples/governance_demo/contract.yaml
seatunnel-agent grants      -d examples/governance_demo --fail-on high
seatunnel-agent ddlguard    -d examples/governance_demo -u undo.sql
seatunnel-agent contract --init -d examples/governance_demo   # 反向生成契约底稿
```
