# 批次结果报告:方言扩展 Phase 3 透传审计(2026-10-31)

## 批准依据

> "指定详细计划后一步步完成"（延续"指定这些数据库的扩展 不要局限于hive"指令的 Phase 3:全仓 --dialect 入口审计）。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | sql_review 支持 oracle:DIALECTS 加 oracle、SQLGLOT_DIALECTS 映射 oracle→oracle、EXECUTOR_DS_TYPES 置 None(无 executor 回退 hive 内省);CLI Choice 随常量自动变宽 | agents/data/sql_review/{linter,ast_check}.py | (本批) |
| 高 | lineage CLI --sql-dialect 两处硬编码 Choice 改为引用 SQL_DIALECTS(单一事实源,oracle/sqlserver 随之可选) | cli_cmds/lineage.py | (本批) |
| 中 | 23 处自由文本 --dialect help 统一点名完整方言集 | cli_cmds/{checks,perf_ops,qo_governance,qo_quality,qo_build,sql_review}.py | (本批) |
| 中 | 前端方言下拉补 oracle/sqlserver(change_impact 有 pinned 测试,data_lineage 同步) | frontend/{change_impact,data_lineage}/src/App.tsx | (本批) |
| 中 | 测试:normalize/is_known oracle、oracle 语法检查、mcp_toolbox 未知方言样例改 sybase | tests/{test_sql_review,test_mcp_toolbox}.py | (本批) |

## 验证结果

```
端到端抽查: review --dialect oracle/sqlserver、lineage --sql-dialect oracle 均 exit 0
python -m pytest tests -q -m "not uitest" -> 4664 passed, 1 skipped, 404 deselected
ruff check src tests -> All checks passed!
npx prettier --check frontend/change_impact/src/App.tsx frontend/data_lineage/src/App.tsx -> All matched files use Prettier code style!
```

```
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## floor 豁免登记

oracle 由非法方言变为合法方言,两条反向断言随行为更新(同文件已补正向断言与新的非法样例 sybase):

floor-waiver: tests/test_sql_review.py: assert not is_known_dialect("oracle")
floor-waiver: tests/test_mcp_toolbox.py: assert "unknown dialect" in tools["sql_review"]("SELECT 1", dialect="oracle")

## 前后差异

- sql_review:10 方言 → 11(oracle 原先静默回退 hive,现按 oracle 解析);test_sql_review 314 → 316 条。
- lineage Choice:硬编码 10 项 → SQL_DIALECTS 12 项。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | skew 两处 --dialect 仍限 spark/maxcompute/hive | cli_cmds/skew.py:26,744 | 倾斜调参建议是引擎特定语义,其他引擎无对应参数 | 无 | 维持 |
| 低 | oracle 无 text2sql executor(EXECUTOR_DS_TYPES=None),schema 内省回退 hive | sql_review/api.py | 执行器未接 oracle | 静态审查不受影响 | 接入 executor 时补 |

## 未执行的步骤

方言扩展三阶段(resolver+evolver+avro2ddl / 调度引擎 / 透传审计)至此完成。
