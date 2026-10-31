# 批次结果报告:Agent 52 实时离线核对 rt_offline_diff(2026-10-31)

## 批准依据

> 用户:"下一批完成这些agent"(48–52)。docs/data_agents_48_52_plan.md
> 里程碑 5:52 rt_offline_diff(套件三收口,48–52 全部完成)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性核对核心:双结果集(复用 sample_profile 解析)按键对齐,共同数值列按相对容差比较 — 双侧缺失键、超差明细(差距大在前,含空值不对称)、系统性偏差判定(同向占比 ≥80%:实时偏低 → 迟到/窗口未闭;偏高 → 重复消费)、一致率 | src/seatunnel_agent/agents/data/rt_offline_diff/comparator.py | 本批 |
| 高 | zh/en 报告 + i18n + LLM 核对通报(opt-in) | rt_offline_diff/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router)+ MCP 工具 + manifest(quality 组) | rt_offline_diff/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent rtoffline`(-r/--offline/-k/--tolerance/--fail-on-diff);修正 -o 与全局 --output 短旗冲突(offline 只保留长旗) | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | React 页(useRunner,双文本框+键/容差输入,demo 预填) | frontend/rt_offline_diff/* + workspace 注册 | 本批 |
| 中 | 示例双结果集 + 单测 19 条 + 页面回归 2 条;计划 5 个里程碑全勾选 | examples/rtoffline_demo/* · tests/test_rt_offline_diff.py · tests/test_rtoffline_page.py · docs/data_agents_48_52_plan.md | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_rt_offline_diff.py -q   -> 19 passed
python -m pytest -m uitest tests/test_rtoffline_page.py -q -> 2 passed
python -m pytest tests -q                           -> 4167 passed, 1 skipped, 332 deselected
seatunnel-agent rtoffline -r realtime.csv --offline offline.csv -k dt,channel -> 一致率 40%,缺失键 1,超差 6,order_cnt/gmv 均判"实时普遍偏低"
npm run build (frontend/rt_offline_diff)            -> built in 2.90s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:quality 组新增 /rtoffline 卡片,REST/MCP/CLI/React 四入口
  齐备;与 data_comparison(连库 checksum)、metric_diff(口径定义)
  分工明确,报告里互相指路。
- 套件三(48 kafka_lag/49 flink_diag/50 rt_latency/51 cdc_diag/52
  rt_offline_diff)五个 agent 全部落地,处方互指成网:flinkdiag →
  kafkalag/skew-runtime,datavolatility → qualitytrace。
- 测试:本批新增 19+2 条;全量 4167 passed(48–52 批次共 +97 条),0 失败。

## 遗留

- 无。48–52 计划收口。
