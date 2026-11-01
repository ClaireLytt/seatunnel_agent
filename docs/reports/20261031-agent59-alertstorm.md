# 批次结果报告:Agent 59 告警风暴聚合 alert_storm(2026-10-31)

## 批准依据

> 用户:"go on"(下一阶段排序 2:59 alert_storm;与 task_failure 分工=
> 任务失败归因 vs 告警通道降噪)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性聚合核心:告警导出(CSV/JSON)按归一化标题签名聚类(复用 task_failure 签名法),头条指标=降噪倍数;AS002 风暴窗口(5 分钟桶超中位数 3 倍且 ≥5 条,点名最猛窗口)、AS003 横跳签名(一小时内 5+ 次,抑制候选)、AS004 吵闹来源(占比 ≥50%) | src/seatunnel_agent/agents/data/alert_storm/analyzer.py | 本批 |
| 高 | zh/en 报告(聚类表 + 通道发现,处方指向 taskfailure/抑制窗口)+ i18n + LLM 交接摘要(opt-in) | alert_storm/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router)+ MCP 工具 + manifest(build 组,order 86) | alert_storm/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent alertstorm`(--llm/--fail-on-high) | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | React 页(useRunner,demo 预填) | frontend/alert_storm/* + workspace 注册 | 本批 |
| 中 | 示例导出 + 单测 18 条 + 页面回归 2 条 | examples/alertstorm_demo/alerts.json · tests/test_alert_storm.py · tests/test_alertstorm_page.py | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_alert_storm.py -q       -> 18 passed
python -m pytest -m uitest tests/test_alertstorm_page.py -q -> 2 passed
python -m pytest tests/test_alert_storm.py tests/test_config_diff.py tests/test_task_failure.py tests/test_hub_pages.py tests/test_mcp_toolbox.py -q -> 99 passed
seatunnel-agent alertstorm -f alerts.json -> 12 条 → 8 件真事(1.5 倍);AS002 抓到 scheduler 5 分钟 6 连发;AS003 抓到 kafka 横跳(40 分钟 5 次)
npm run build (frontend/alert_storm)                -> built in 2.89s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:build 组新增 /alertstorm 卡片,REST/MCP/CLI/React 四入口
  齐备;设计取舍:不同任务名的同型告警不硬并签名,交给 AS002 时间窗归并
  成事故单(避免过度合并),降噪倍数保持诚实。
- 测试:新增 18 条单测 + 2 条页面回归,全部通过;相关套件 99 passed 无回归。

## 遗留

- 下一阶段排序继续:60 metric_attribution → 增强(--history ×2)→ 61–64。
