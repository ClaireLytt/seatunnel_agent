# 批次结果报告:方言扩展 Phase 1(2026-10-31)

## 批准依据

> 用户给出技术栈清单(MySQL/PostgreSQL/Oracle/SQL Server/Hive/Spark/MaxCompute/Flink/Kafka/SeaTunnel/DataX/Sqoop/Airflow/DolphinScheduler/Azkaban)并指示:"指定这些数据库的扩展 不要局限于hive"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | sqlglot 方言解析新增 oracle/sqlserver/mssql/tsql 别名,SQL_DIALECTS 扩表 | src/seatunnel_agent/agents/data/data_lineage/sqlglot_lineage.py | (本批) |
| 高 | ddl_evolve 按 family(hivelike/mysql/doris/postgres/oracle/tsql)生成 8 方言迁移脚本:ADD/CHANGE/MODIFY/ALTER COLUMN、sp_rename、COMMENT ON 按方言拼写 | src/seatunnel_agent/agents/data/ddl_evolve/evolver.py | (本批) |
| 高 | avro2ddl 按 family 建表:各方言类型映射(TEXT/BYTEA/JSONB/NUMBER/VARCHAR2/NVARCHAR(MAX)/DATETIME2 等)、注释能力分化(inline / COMMENT ON / tsql 丢弃)、复杂类型落 JSON/JSONB/CLOB/NVARCHAR(MAX) | src/seatunnel_agent/agents/data/avro2ddl/converter.py | (本批) |
| 中 | CLI 两处 --dialect 选项扩到 8 方言 | src/seatunnel_agent/cli_cmds/qo_build.py | (本批) |
| 中 | 新增/更新方言测试(evolver 16 条、converter 14 条) | tests/test_ddl_evolve.py, tests/test_avro2ddl.py | (本批) |

## 验证结果

```
python -m pytest tests/test_avro2ddl.py tests/test_ddl_evolve.py tests/test_data_lineage.py tests/test_schema_drift.py -q
  -> 209 passed, 1 skipped in 6.94s
ruff check src tests -> All checks passed!
python scripts/check_workflow.py ->(提交后输出见下)
```

```
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- ddl_evolve:2 方言(hive/mysql)→ 8 方言;测试 11 → 16 条。
- avro2ddl:2 方言(hive/doris)→ 8 方言;测试 11 → 14 条;CLI choice 与 converter 校验一致。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | oracle VARCHAR 变宽被 sqlglot 归一为 VARCHAR2,widening 规则未命中,MODIFY 以注释形式输出 | tests/test_ddl_evolve.py::test_oracle_and_sqlserver_spellings | sqlglot oracle 渲染差异 | 变更仍输出,仅需人工取消注释 | 维持保守行为 |
| 低 | tsql 列注释无可移植拼写,降级为 informational 注释行 | evolver/_set_comment | T-SQL 以 sp_addextendedproperty 管注释 | 注释不落库 | 维持 |

## 未执行的步骤

Phase 2(dag_gen --engine dolphinscheduler/azkaban)与 Phase 3(其余 agent 的 --dialect 透传审计)待下一批。
