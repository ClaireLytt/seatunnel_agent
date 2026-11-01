# 批次结果报告:Agent 38 质量根因追踪 quality_trace(2026-10-31)

## 批准依据

> 用户:"适配以上的agent 制定好方案后一步步执行"(36–47 清单)。
> docs/data_agents_36_47_plan.md 里程碑 5:38 quality_trace(复用
> data_lineage 解析器)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性追踪核心:SQL 脚本 → data_lineage 血缘图(临时目录缓存,不污染 logs/)→ 上溯打嫌疑分(距离衰减、列级污染路径 +40、变换表达式 +10、不在路径降权),每个嫌疑附变换点与验证 SQL | src/seatunnel_agent/agents/data/quality_trace/tracer.py | 本批 |
| 高 | zh/en 报告(嫌疑排行 + 前 3 验证 SQL 代码块)+ i18n + LLM 追踪通报(opt-in) | quality_trace/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router)+ MCP 工具 + manifest | quality_trace/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent qualitytrace`(-t/-c/--symptom/--dialect/--llm) | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | React 页(useRunner,SQL+表/列/症状输入,demo 预填) | frontend/quality_trace/* + workspace 注册 | 本批 |
| 中 | 示例流水线 SQL + 单测 18 条 + 页面回归 2 条 | examples/qualitytrace_demo/pipeline.sql · tests/test_quality_trace.py · tests/test_qualitytrace_page.py | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_quality_trace.py -q     -> 18 passed
python -m pytest -m uitest tests/test_qualitytrace_page.py -q -> 2 passed
python -m pytest tests/test_quality_trace.py tests/test_data_volatility.py tests/test_dup_check.py tests/test_dist_anomaly.py tests/test_sample_profile.py tests/test_hub_pages.py tests/test_mcp_toolbox.py -q -> 147 passed
seatunnel-agent qualitytrace -f pipeline.sql -t dws.orders_daily -c gmv -> 嫌疑排行 dwd.orders(100)>ods.orders_raw(83)>dim.users(20,降权)
npm run build (frontend/quality_trace)              -> built in 2.97s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:quality 组新增 /qualitytrace 卡片,REST/MCP/CLI/React 四入口
  齐备;血缘解析复用 data_lineage(零重写),38 只新增"质量事件 × 血缘"
  叠加判定,与查重结论一致。
- 测试:新增 18 条单测 + 2 条页面回归,全部通过;相关套件 147 passed 无回归。

## 遗留

- 里程碑 6(40 data_repair,套件一收口)与 42–47 继续按计划落地。
