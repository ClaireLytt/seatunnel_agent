# 批次结果报告:Agent 54 调度窗口优化 schedule_advisor(2026-10-31)

## 批准依据

> 用户:"think about new functions"后"按你的排序执行"(排序中 53 之后为
> 54 schedule_advisor:时长 × 依赖 → 排程建议,与 dag_conflict 的冲突
> 检测互补)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性排程核心:计划 JSON(day_start/tasks 时长与依赖/可选 SLA)→ 最早排程(环检测)、SLA 余量(偏薄 <30min/破线点名)、关键路径回溯、SLA 祖先的松弛分钟、并行峰值窗口与可错峰清单(松弛 ≥60min) | src/seatunnel_agent/agents/data/schedule_advisor/advisor.py | 本批 |
| 高 | zh/en 报告(时间线表,关键任务标注)+ i18n + LLM 排程通报(opt-in) | schedule_advisor/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router)+ MCP 工具 + manifest(build 组,order 81) | schedule_advisor/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent scheduleadvisor`(--fail-on-breach:余量为负 exit 1) | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | React 页(useRunner,demo 预填) | frontend/schedule_advisor/* + workspace 注册 | 本批 |
| 中 | 示例计划 + 单测 16 条 + 页面回归 2 条 | examples/scheduleadvisor_demo/plan.json · tests/test_schedule_advisor.py · tests/test_scheduleadvisor_page.py | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_schedule_advisor.py -q  -> 16 passed
python -m pytest -m uitest tests/test_scheduleadvisor_page.py -q -> 2 passed
python -m pytest tests/test_schedule_advisor.py tests/test_task_failure.py tests/test_hub_pages.py tests/test_mcp_toolbox.py -q -> 80 passed
seatunnel-agent scheduleadvisor -f plan.json -> 完成 04:05/余量 175min,关键路径 4 任务,dim_users 松弛 35min,峰值 3@01:10
npm run build (frontend/schedule_advisor)           -> built in 3.41s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:build 组新增 /scheduleadvisor 卡片,REST/MCP/CLI/React
  四入口齐备;与 dag_conflict 分工明确(资源冲突检测 vs 排程时间建议)。
- 测试:新增 16 条单测 + 2 条页面回归,全部通过;相关套件 80 passed 无回归。

## 遗留

- 排序最后一项:C 套件总览导航页。
