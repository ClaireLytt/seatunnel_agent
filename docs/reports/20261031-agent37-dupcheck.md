# 批次结果报告:Agent 37 数据重复检测 dup_check(2026-10-31)

## 批准依据

> 用户:"适配以上的agent 制定好方案后一步步执行"(36–47 清单)。
> docs/data_agents_36_47_plan.md 里程碑 3:37 dup_check。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性检测核心:全行/主键/业务键三层重复组,每组带行数、首末行号与差异列(定位来源);全行组不在键层重复报;键为空的行跳过 | src/seatunnel_agent/agents/data/dup_check/detector.py | 本批 |
| 高 | zh/en 报告(含来源处方提示)+ i18n + LLM 去重通报(opt-in) | dup_check/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router)+ MCP 工具 + manifest | dup_check/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent dupcheck`(--pk/--biz-key/--llm/--fail-on-dup) | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | React 页(useRunner,主键/业务键输入,demo 预填) | frontend/dup_check/* + workspace 注册 | 本批 |
| 中 | 示例数据 + 单测 19 条 + 页面回归 2 条 | examples/dupcheck_demo/events.csv · tests/test_dup_check.py · tests/test_dupcheck_page.py | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_dup_check.py -q         -> 19 passed
python -m pytest -m uitest tests/test_dupcheck_page.py -q -> 2 passed
python -m pytest tests/test_dup_check.py tests/test_dist_anomaly.py tests/test_sample_profile.py tests/test_hub_pages.py tests/test_mcp_toolbox.py -q -> 110 passed
seatunnel-agent dupcheck -f events.csv --pk event_id --biz-key user_id,action,amount -> 4 组(全行/主键/业务键×2),差异列正确定位 source/created_at
npm run build (frontend/dup_check)                  -> built in 2.89s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:quality 组新增 /dupcheck 卡片,REST/MCP/CLI/React 四入口齐备;
  与 data_quality.unique 分工明确(违规计数 vs 重复组明细定位)。
- 测试:新增 19 条单测 + 2 条页面回归,全部通过;相关套件 110 passed 无回归。

## 遗留

- 里程碑 4–12(39/38/40 与 42–47)继续按计划逐个落地。
