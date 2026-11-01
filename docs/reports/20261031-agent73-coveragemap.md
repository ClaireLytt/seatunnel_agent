# Agent 73 coverage_map — 质量覆盖地图

日期: 2026-10-31 分支: fresh

## 内容

- 脚手架起步。`agents/data/coverage_map/`：mapper（三解析器复用:schema_drift DDL + data_quality 规则 + contract_check 契约）、i18n、report、advisor_llm（可选补洞计划）、api、tools、manifest（group governance, /coveragemap）。
- 地图：DDL 全表 × 已配置的闸——逐表标出 row_count/null_rate/unique/enum_domain 计数与契约有无;裸奔在前;总体覆盖率置顶。
- 分级：CM001 裸奔表（热层 dwd/dws/ads 记 high——消费方直接挨刀;其余 medium）;CM002 死闸（规则或契约声明的表不在 DDL,守着空城,点名工件类型）。
- 闭环收口：dq_rulegen/contract_gen **生成**闸,data_quality/contract_check **执行**闸,本 agent 回答"闸到底铺到哪了"。
- 输入校验：至少给一个闸工件;规则 YAML 解析错误原样上抛。
- CLI `coveragemap`（--ddl/--rules/--contract/--llm/--fail-on-high gate,热层裸奔即 exit 1）。
- 测试：`tests/test_coverage_map.py` 11 项（覆盖率/热层分级/死闸双工件/单工件模式/clean/gate）;页面 spec 2 项。
- 示例 `examples/coveragemap_demo/{warehouse.sql,rules.yaml,contract.yaml}`（50% 覆盖 + 热层裸奔 + 死闸齐打）。

## 验证

```
tests\test_coveragemap_page.py ..                                        [100%]
============================== 2 passed in 9.26s ==============================

tests/test_coverage_map.py + test_data_quality.py + test_contract_check.py
  + test_registry.py + test_hub_pages.py + test_collision_guards.py
======================= 84 passed, 2 warnings in 16.00s =======================
All checks passed!   (ruff)
```

前端 `npm run lint` 零告警，`npm run build` 成功。

## Gate

```
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```
