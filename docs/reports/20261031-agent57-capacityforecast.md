# 批次结果报告:Agent 57 容量耗尽预测 capacity_forecast(2026-10-31)

## 批准依据

> 用户:"go on"(55–59 候选排序,56 之后为 57:存储序列 × 配额 →
> 耗尽日期;与 storage_cost 分工=现在清什么 vs 什么时候爆)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性预测核心:复用 data_volatility.parse_series,逐指标最近 window(默认 14)点最小二乘斜率(ISO 日期按真实天偏移),total 指标直用否则求和;线性外推耗尽日期,CF001 视界告警(90 天中/30 天高/已超额=0 天)、CF002 增长大户(含净增速占比)、CF003 缩小指标 | src/seatunnel_agent/agents/data/capacity_forecast/forecaster.py | 本批 |
| 高 | zh/en 报告(线性外推假设明示)+ i18n + LLM 容量通报(opt-in) | capacity_forecast/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router,quota/window 参数)+ MCP 工具 + manifest(governance 组,order 84) | capacity_forecast/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent capacityforecast`(--quota/--window/--fail-on-high) | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | React 页(useRunner,序列+配额输入,demo 预填) | frontend/capacity_forecast/* + workspace 注册 | 本批 |
| 中 | 示例序列(涨/缓涨/缩三表)+ 单测 17 条(含固定 today 的日期数学)+ 页面回归 2 条 | examples/capacityforecast_demo/storage.csv · tests/test_capacity_forecast.py · tests/test_capacityforecast_page.py | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_capacity_forecast.py -q -> 17 passed
python -m pytest -m uitest tests/test_capacityforecast_page.py -q -> 2 passed
python -m pytest tests/test_capacity_forecast.py tests/test_partition_health.py tests/test_hub_pages.py tests/test_mcp_toolbox.py -q -> 82 passed
seatunnel-agent capacityforecast -f storage.csv --quota 2000 -> 总量 1060、+20/天、47 天后 2026-12-17 耗尽(中);大户 click_log 100%;bak 在缩小
npm run build (frontend/capacity_forecast)          -> built in 2.91s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:governance 组新增 /capacityforecast 卡片,REST/MCP/CLI/React
  四入口齐备;序列解析零重写(39 门面复用),与 45 形成"何时爆 → 清什么"
  衔接。
- 测试:新增 17 条单测 + 2 条页面回归,全部通过;相关套件 82 passed 无回归。

## 遗留

- 候选排序继续:58 config_diff → 59 alert_storm → 增强(--history ×2)。
