# 批次结果报告:metaquality-rules(2026-10-29)

## 批准依据

> 功能盘点轮用户批示:"go on"(推荐方案第 3 项:metadata_quality 新规则,不开新 agent)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 新规则 unpartitioned_fact(medium):dwd/dws 层表无 PARTITIONED BY;dim/ods/ads 刻意不报(小维表/服务表合法无分区,吸取 layer_naming 噪音教训) | metadata_quality/checker.py | 本批次 |
| 高 | 新规则 money_string(medium):金额命名列用 STRING,与既有 money_float(high)互补 | metadata_quality/checker.py | 本批次 |
| 中 | 报告双语标签 + 2 条单测(分层豁免矩阵、列级命中) | metadata_quality/report.py, tests/test_metadata_quality.py | 本批次 |
| 低 | 治理指南同步两条规则 | docs/governance_guide.md | 本批次 |

计划里的第三条(lifecycle/TTL 缺失)不做:TBLPROPERTIES 语义按引擎各异
(MaxCompute lifecycle / Hive retention),静态判定噪音大于信号。

## 验证结果

```
python -m pytest tests/test_metadata_quality.py tests/test_contract_check.py tests/test_mcp_toolbox.py -q
  -> 63 passed in 13.81s
python -m pytest -q  -> 3596 passed, 1 skipped, 262 deselected in 149.61s
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

无 UI 改动(规则经既有 /metaquality 页与报告渲染自动生效)。

## 前后差异

- 规则数 4 → 6;全量测试 3594 → 3596(+2)。既有测试零改动通过——
  新规则未污染现有断言(噪音控制生效)。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- grant_scan(权限面扫描)为盘点轮的候选 2,等 contract_check 用起来后再议。
