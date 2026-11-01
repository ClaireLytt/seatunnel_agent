# 批次结果报告:Agent 49 Flink 作业诊断 flink_diag(2026-10-31)

## 批准依据

> 用户:"下一批完成这些agent"(48–52)。docs/data_agents_48_52_plan.md
> 里程碑 2:49 flink_diag。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性诊断核心:作业快照 JSON(各节可选)→ FD001–FD006 — checkpoint 失败(最近失败/≥3 次为高)、时长暴涨(60/300s 或 2 倍中位数)、对齐耗时主导(≥50% 建议 unaligned)、背压算子(0.5/0.8,取最重)、watermark 滞后(60/300s)、频繁重启(1/3 次每小时附最后原因) | src/seatunnel_agent/agents/data/flink_diag/diagnoser.py | 本批 |
| 高 | zh/en 报告(处方指向 kafkalag/skew-runtime)+ i18n + LLM 运维通报(opt-in) | flink_diag/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router)+ MCP 工具 + manifest(quality 组) | flink_diag/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent flinkdiag`(--llm/--fail-on-high) | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | React 页(useRunner,demo 预填) | frontend/flink_diag/* + workspace 注册 | 本批 |
| 中 | 示例快照 + 单测 19 条 + 页面回归 2 条 | examples/flinkdiag_demo/snapshot.json · tests/test_flink_diag.py · tests/test_flinkdiag_page.py | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_flink_diag.py -q        -> 19 passed
python -m pytest -m uitest tests/test_flinkdiag_page.py -q -> 2 passed
python -m pytest tests/test_flink_diag.py tests/test_kafka_lag.py tests/test_hub_pages.py tests/test_mcp_toolbox.py -q -> 87 passed
seatunnel-agent flinkdiag -f snapshot.json -> 6 条发现(FD004/005 高),14.6 倍暴涨与 64.2% 对齐占比正确
npm run build (frontend/flink_diag)                 -> built in 3.23s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:quality 组新增 /flinkdiag 卡片,REST/MCP/CLI/React 四入口
  齐备;与 skew-runtime 互补(task 级倾斜 vs 作业健康面),处方互指。
- 测试:新增 19 条单测 + 2 条页面回归,全部通过;相关套件 87 passed 无回归。

## 遗留

- 里程碑 3–5(50 rt_latency、51 cdc_diag、52 rt_offline_diff)继续落地。
