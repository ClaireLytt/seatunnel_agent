# Agent 77 sla_board — SLA 达成看板

日期: 2026-10-31 分支: fresh

## 内容

- `agents/data/sla_board/`：board（复用 sample_profile.parse_rows）、i18n、report、advisor_llm（可选 SLA 通报）、api（make_text_router）、tools（MCP）、manifest（group build, /slaboard）。
- 输入：完成记录（task/date/deadline/finish）,时间接受 HH:MM（过午夜可写 25:30,调度惯例）或 ISO datetime。
- 指标：逐任务达成率、迟到 p50/p90/最差（只统计迟到场次）、最长与**当前**连续破线;看板最差在前。
- 分级：SL001 达成率低于目标（<80% high,否则 medium）;SL002 正处于 ≥3 天连续破线（high）;SL003 迟到 p90 >60 分钟慢性迟到（medium）。
- 边界：schedule_advisor 管怎么排、task_failure 管为何挂,本 agent 管"按时"这条对外承诺。
- CLI `slaboard`：--target、--history（track_history 台账,worse_key=misses）、--trend N + --fail-on-trend（rising_trend 复用）、--fail-on-high、--llm,与 dbdiag/kafkalag 同一台账模式。
- React 页面 `frontend/sla_board/`：记录输入 + 目标 + LLM 复选框,演示预填三任务（连续破线/边缘迟到/全绿）。
- 测试：`tests/test_sla_board.py` 12 项（demo 指标、分级、过午夜与 ISO 时间、streak 重置、台账写入、trend gate）;`tests/test_slaboard_page.py` 双页面流。
- 示例 `examples/slaboard_demo/runs.csv`。

## 验证

```
tests\test_slaboard_page.py ..                                           [100%]
============================== 2 passed in 7.62s ==============================

tests/test_sla_board.py + test_registry.py + test_hub_pages.py
======================= 47 passed, 2 warnings in 13.52s =======================
All checks passed!   (ruff)
```

前端 `npm run lint` 零告警，`npm run build` 成功。

## Gate

```
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```
