# 批次结果报告:Agent 56 分区健康体检 partition_health(2026-10-31)

## 批准依据

> 用户:"go on"(55–59 候选排序,55 之后为 56:分区本身的健康,与
> data_freshness 的"按时到"分工明确)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性体检核心:分区清单(CSV/JSON)按表分组 → PH001 日期断档(回刷洞)/PH002 空分区/PH003 大小倾斜(5/20 倍表中位数,需 ≥4 个有量分区)/PH004 最新分区暴涨(3/10 倍)/PH005 缩水(<0.3 倍);非日期分区静默跳过日期规则 | src/seatunnel_agent/agents/data/partition_health/analyzer.py | 本批 |
| 高 | zh/en 报告(处方指向 backfill/dupcheck/datavolatility)+ i18n + LLM 分区通报(opt-in) | partition_health/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router)+ MCP 工具 + manifest(quality 组,order 83) | partition_health/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent partitionhealth`(--llm/--fail-on-high) | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | React 页(useRunner,demo 预填) | frontend/partition_health/* + workspace 注册 | 本批 |
| 中 | 示例清单 + 单测 17 条 + 页面回归 2 条 | examples/partitionhealth_demo/partitions.csv · tests/test_partition_health.py · tests/test_partitionhealth_page.py | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_partition_health.py -q  -> 17 passed
python -m pytest -m uitest tests/test_partitionhealth_page.py -q -> 2 passed
python -m pytest tests/test_partition_health.py tests/test_layer_check.py tests/test_hub_pages.py tests/test_mcp_toolbox.py -q -> 84 passed
seatunnel-agent partitionhealth -f partitions.csv -> PH001–PH005 五规则全中(断档 10-27+2/空 10-28/倾斜与暴涨 11.7 倍/缩水 0.3)
npm run build (frontend/partition_health)           -> built in 2.83s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:quality 组新增 /partitionhealth 卡片,REST/MCP/CLI/React
  四入口齐备;"分区本身健不健康"此前无覆盖(freshness 只管按时到)。
- 测试:新增 17 条单测 + 2 条页面回归,全部通过;相关套件 84 passed 无回归。

## 遗留

- 候选排序继续:57 capacity_forecast → 58 config_diff → 59 alert_storm
  → 增强(dbdiag/taskfailure --history)。
