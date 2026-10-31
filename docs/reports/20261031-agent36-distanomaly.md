# 批次结果报告:Agent 36 数据分布异常 dist_anomaly(2026-10-31)

## 批准依据

> 用户:"适配以上的agent 制定好方案后一步步执行"(36–47 清单)。
> docs/data_agents_36_47_plan.md 里程碑 2:36 dist_anomaly(复用 41 的
> profiler)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性对比核心:两侧输入(原始 CSV/JSONL 或 profile JSON)→ DA001–DA007 漂移规则(schema 增删、均值 ±20/50%、空值/唯一率 ±10/25pp、类别 L1 0.2/0.4 附移动最大类别、新增/消失类别、主类型变化) | src/seatunnel_agent/agents/data/dist_anomaly/comparator.py | 本批 |
| 高 | zh/en 报告 + i18n + LLM 漂移通报(opt-in) | dist_anomaly/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router)+ MCP 工具 + manifest | dist_anomaly/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent distanomaly`(-b/-c/--max-rows/--llm/--fail-on-high) | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | React 页(useRunner,基线/当前双文本框,demo 预填) | frontend/dist_anomaly/* + workspace 注册 | 本批 |
| 中 | 示例数据对 + 单测 19 条 + 页面回归 2 条 | examples/distanomaly_demo/{baseline,current}.csv · tests/test_dist_anomaly.py · tests/test_distanomaly_page.py | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_dist_anomaly.py -q      -> 19 passed
python -m pytest -m uitest tests/test_distanomaly_page.py -q -> 2 passed
python -m pytest tests/test_dist_anomaly.py tests/test_sample_profile.py tests/test_hub_pages.py tests/test_mcp_toolbox.py -q -> 91 passed
seatunnel-agent distanomaly -b baseline.csv -c current.csv -> 6 条发现(DA001×2/DA002/DA003/DA004/DA005)
npm run build (frontend/dist_anomaly)               -> built in 2.87s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:quality 组新增 /distanomaly 卡片,REST/MCP/CLI/React 四入口齐备;
  与 data_quality 分工明确(规则阈值体检 vs 无规则分布漂移对比)。
- 测试:新增 19 条单测 + 2 条页面回归,全部通过;相关套件 91 passed 无回归。

## 遗留

- 里程碑 3–12(37/39/38/40 与 42–47)继续按计划逐个落地。
