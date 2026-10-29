# 批次结果报告:contract-check(2026-10-29)

## 批准依据

> 功能盘点轮用户批示:"go on"(对「1 contract_check 新 agent + 3 metadata_quality 新规则」的推荐方案放行)。本批次先交付 1;3 在下一批次。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | contract_check agent 核心:YAML 契约解析 + DDL 对照(表/列缺失、类型违约 high;分区违约 medium;缺注释/契约外列 low),复用 schema_drift 解析器 | agents/data/contract_check/{checker,report}.py | 本批次 |
| 高 | CLI `contract`(CheckSpec 一个声明)、REST `/api/contract/scan`(ScanSpec + contract 必填扩展字段)、聊天/MCP 工具(manifest 一处声明) | cli_cmds/checks.py, contract_check/{api,tools,manifest}.py | 本批次 |
| 高 | React 页 /contract(契约 YAML + 目录/粘贴 DDL 双入口,照 metaquality 版式) | frontend/contract_check/ | 本批次 |
| 中 | 19 条单测(契约解析/分级/前缀类型匹配/CLI 门禁/REST/发现接线)+ 3 条 Playwright 页测 | tests/test_contract_check.py, tests/test_contract_page.py | 本批次 |
| 低 | 治理指南加「承诺:数据契约」一节 | docs/governance_guide.md | 本批次 |

## 验证结果

```
python -m pytest tests/test_contract_check.py -q        -> 19 passed in 6.36s
python -m pytest -m uitest tests/test_contract_page.py  -> 3 passed in 15.18s
npm run build --workspace contract_check                -> built in 3.51s
npm run lint --workspace contract_check                 -> clean
python -m pytest -q  -> 3594 passed, 1 skipped, 262 deselected in 152.51s
ruff check src tests -> All checks passed!
mypy                 -> Success: no issues found in 177 source files
```

```
check_workflow 输出(提交后运行):
[PASS] AI 署名: 无 AI 署名(范围 origin/pso..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘
[PASS] 报告含验证输出
[PASS] floor: 无作弊变绿改动(范围 origin/pso..HEAD)
```

## 前后差异

- 新增 agent 一次点亮四个面(CLI/REST/MCP+编排/React 页),注册只动了两个自家文件 + checks.py 一个命令——昨天的三个 seam(ScanSpec/CheckSpec/ToolManifest)的第一个真实消费者,test_mcp_toolbox 的结构断言零改动自动覆盖新工具。
- 与 schema_drift 的分界:drift 比两版 DDL,contract 比「声明的期望 vs 现状」;与 metaquality 的分界:通用规约 vs 项目自己的约定。
- 全量测试 3575 → 3594(+19),uitest 259 → 262(+3)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 契约暂无「禁删列/只增不改」时序性断言 | checker.py | 需要基线版本概念,属 schema_drift 领域 | 可用 drift + contract 组合覆盖 | 需求出现再议 |

## 未执行的步骤

- metadata_quality 新规则(unpartitioned_fact 等)在下一批次。
