# 批次结果报告:governance-overview(2026-10-29)

## 批准依据

> 用户批示:"go on"(执行 NEXT.md 待办「治理总览页 /governance」:三个新 agent 补 RunLogger + stats REST + 聚合页面)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | contract/grants/ddlguard 补 RunLogger 适配器(命名 + summarize 各 ~25 行),CLI 与 REST 双 source 落档;ddlguard 的 CLI 钩子与回滚落盘共用 log_run | 三个 history.py, cli_cmds/checks.py, 三个 api.py | 本批次 |
| 高 | ScanSpec 新增 log_recent → seam 自动生成 GET /stats(n 夹在 1-200);五个治理 agent 全部接上 | common/scan_api.py, 五个 api.py | 本批次 |
| 高 | /governance 总览页:五张卡 = 最新 high/medium/low/total 徽标 + SVG 趋势折线 + 运行次数与首末对比;无记录的 agent 安静显示空态;卡头直链各 agent 页 | agents/data/governance_overview/, frontend/governance_overview/ | 本批次 |
| 中 | 测试:三个 agent 各一条「CLI+API 双 source 落档 + /stats 返回」;总览页 Playwright(种子 hygiene 历史渲染趋势,其余四卡空态,404 之外零控制台错误) | tests/test_{contract_check,grant_scan,ddl_guard}.py, tests/test_governance_page.py | 本批次 |
| 低 | 指南「度量」节补 stats 端点与总览页;NEXT.md 待办清掉 | docs/governance_guide.md, docs/NEXT.md | 本批次 |

## 验证结果

```
python -m pytest tests/test_contract_check.py tests/test_grant_scan.py tests/test_ddl_guard.py -q
  -> 45 passed in 4.42s
python -m pytest -m uitest tests/test_governance_page.py -q -> 1 passed in 8.99s
npm run build --workspace governance_overview               -> built in 3.13s
npm run lint --workspace governance_overview                -> clean
python -m pytest -q  -> 3625 passed, 1 skipped, 267 deselected in 165.67s
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

- 度量面闭环:五个治理 agent 的历史从「两个有、三个没有」补齐为全覆盖;stats REST 由 ScanSpec seam 一处生成(每个 agent 只加一行 log_recent)。
- 总览页是 page-only 插件(manifest 无 api 字段),数据全部走各 agent 自己的 /stats——总览不持有任何状态。
- 全量测试 3622 → 3625(+3),uitest 266 → 267(+1)。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

无。
