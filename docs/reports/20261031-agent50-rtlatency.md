# 批次结果报告:Agent 50 实时延迟分析 rt_latency(2026-10-31)

## 批准依据

> 用户:"下一批完成这些agent"(48–52)。docs/data_agents_48_52_plan.md
> 里程碑 3:50 rt_latency。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性分析核心:事件时间戳行(CSV/JSONL,*_ts 列定义流水线阶段,后段可缺省、事件内桥接缺失段)→ 分段与端到端 p50/p95/max、主导段、离群事件(> 3 倍中位数附最慢段)、SLA 破线数;ISO/epoch 秒/毫秒自适应,负间隔按 0 计 | src/seatunnel_agent/agents/data/rt_latency/analyzer.py | 本批 |
| 高 | zh/en 报告(主导段加粗)+ i18n + LLM 延迟通报(opt-in) | rt_latency/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router)+ MCP 工具 + manifest(quality 组) | rt_latency/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent rtlatency`(--sla-ms/--fail-on-breach/--llm) | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | React 页(useRunner,SLA 输入,demo 预填) | frontend/rt_latency/* + workspace 注册 | 本批 |
| 中 | 示例事件 + 单测 19 条 + 页面回归 2 条 | examples/rtlatency_demo/events.csv · tests/test_rt_latency.py · tests/test_rtlatency_page.py | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_rt_latency.py -q        -> 19 passed
python -m pytest -m uitest tests/test_rtlatency_page.py -q -> 2 passed
python -m pytest tests/test_rt_latency.py tests/test_flink_diag.py tests/test_kafka_lag.py tests/test_hub_pages.py tests/test_mcp_toolbox.py -q -> 106 passed
seatunnel-agent rtlatency -f events.csv --sla-ms 2000 -> 主导段 ingest→process,离群 e008(73.4s),破线 1
npm run build (frontend/rt_latency)                 -> built in 2.92s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:quality 组新增 /rtlatency 卡片,REST/MCP/CLI/React 四入口
  齐备;与 data_freshness/sla_trace 分工明确(事件级链路延迟 vs 批表
  按时性 vs 调度关键路径)。离群判定从含离群值的 p95 改为 3 倍中位数
  (小样本下单个巨值会抬高 p95 使规则失灵)。
- 测试:新增 19 条单测 + 2 条页面回归,全部通过;相关套件 106 passed 无回归。

## 遗留

- 里程碑 4–5(51 cdc_diag、52 rt_offline_diff)继续落地。
