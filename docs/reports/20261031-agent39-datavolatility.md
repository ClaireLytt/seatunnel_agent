# 批次结果报告:Agent 39 数据波动分析 data_volatility(2026-10-31)

## 批准依据

> 用户:"适配以上的agent 制定好方案后一步步执行"(36–47 清单)。
> docs/data_agents_36_47_plan.md 里程碑 4:39 data_volatility。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性分析核心:date,metric,value 序列(CSV/JSONL 多指标)→ VA001–VA005(突增 7 点滚动中位数+MAD 分级 +50/100%、突降 -30/60%、水平位移 ±30/60%、走平、日期断档);同向连跌/连涨只报首点,持续水平交给 VA003 | src/seatunnel_agent/agents/data/data_volatility/analyzer.py | 本批 |
| 高 | zh/en 报告(处方指向 qualitytrace)+ i18n + LLM 波动通报(opt-in) | data_volatility/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router)+ MCP 工具 + manifest | data_volatility/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent datavolatility`(--llm/--fail-on-high) | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | React 页(useRunner,demo 预填) | frontend/data_volatility/* + workspace 注册 | 本批 |
| 中 | 示例序列 + 单测 19 条 + 页面回归 2 条 | examples/datavolatility_demo/daily_orders.csv · tests/test_data_volatility.py · tests/test_datavolatility_page.py | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_data_volatility.py -q   -> 19 passed
python -m pytest -m uitest tests/test_datavolatility_page.py -q -> 2 passed
python -m pytest tests/test_data_volatility.py tests/test_dup_check.py tests/test_dist_anomaly.py tests/test_sample_profile.py tests/test_hub_pages.py tests/test_mcp_toolbox.py -q -> 129 passed
seatunnel-agent datavolatility -f daily_orders.csv  -> VA001 order_cnt 高 / VA002+VA003 gmv / VA004 active_users / VA005 断档
npm run build (frontend/data_volatility)            -> built in 2.85s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:quality 组新增 /datavolatility 卡片,REST/MCP/CLI/React 四入口
  齐备;与 data_freshness 分工明确(按时到 vs 值对不对)。
- 测试:新增 19 条单测 + 2 条页面回归,全部通过;相关套件 129 passed 无回归。

## 遗留

- 里程碑 5–12(38/40 与 42–47)继续按计划逐个落地。
