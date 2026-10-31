# 批次结果报告:Agent 60 指标异动归因 metric_attribution(2026-10-31)

## 批准依据

> 用户:"think about new functions"后"go on"(合并队列排序 1:60
> metric_attribution — "昨天 GMV 为什么跌、哪个渠道贡献的")。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性归因核心:双结果集(复用 sample_profile 解析)按维度逐值求和,变动精确可加分解为贡献额与占比(含新出现/消失的值);MA001 头号贡献、MA002 高度集中(单值 ≥50%,单点事故)、MA003 结构漂移(涨跌对冲 ≥1.5 倍净额) | src/seatunnel_agent/agents/data/metric_attribution/attributor.py | 本批 |
| 高 | zh/en 报告(发现 + 逐维度分解表,处方指向 qualitytrace)+ i18n + LLM 归因回复(opt-in) | metric_attribution/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router)+ MCP 工具 + manifest(quality 组,order 87) | metric_attribution/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent metricattr`(-b/-c/--dims/--metric/--llm) | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | React 页(useRunner,双结果集+维度/指标输入,demo 预填) | frontend/metric_attribution/* + workspace 注册 | 本批 |
| 中 | 示例双切片 + 单测 17 条(含可加性恒等式断言)+ 页面回归 2 条 | examples/metricattribution_demo/* · tests/test_metric_attribution.py · tests/test_metricattribution_page.py | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_metric_attribution.py -q -> 17 passed
python -m pytest -m uitest tests/test_metricattribution_page.py -q -> 2 passed
python -m pytest tests/test_metric_attribution.py tests/test_alert_storm.py tests/test_hub_pages.py tests/test_mcp_toolbox.py -q -> 83 passed
seatunnel-agent metricattr -b baseline.csv -c current.csv --dims channel,region --metric gmv -> GMV -13000(-8.67%),app 贡献 -15500(119.2%)/north -13500,MA002 单点判定正确
npm run build (frontend/metric_attribution)         -> built in 2.91s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:quality 组新增 /metricattribution 卡片,REST/MCP/CLI/React
  四入口齐备;补齐"39 检出异动 → 60 维度归因 → 38 血缘根因"完整链路。
- 测试:新增 17 条单测(可加性恒等式保证分解精确)+ 2 条页面回归,全部
  通过;相关套件 83 passed 无回归。

## 遗留

- 队列继续:65 schema_align → 增强(--history ×2)→ 66–69、61–64。
