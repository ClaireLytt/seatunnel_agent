# Agent 72 incident_review — 事故复盘

日期: 2026-10-31 分支: fresh

## 内容

- 脚手架起步。`agents/data/incident_review/`：reviewer（复用 sample_profile.parse_rows）、i18n、report、advisor_llm（可选复盘文档草稿,blameless 口径）、api、tools、manifest（group build, /incidentreview）。
- 输入：事故事件日志（time/kind/text,kind ∈ impact|alert|action|comm|recovery）;时间 HH:MM 或 ISO,**同一粘贴只允许一种格式**（沿用 sla_board 评审教训,混用直接 ValueError）;乱序行自动按时间排序,时间线归一为 T+分钟。
- 指标：MTTD（影响→首个告警）、MTTA（告警→首个处置）、MTTR（影响→最后恢复）——按记录计算而非回忆。
- 分级：IR001 发现滞后 ≥15 分（≥4 倍 high）;IR002 响应滞后同规则;IR003 事故中段 ≥30 分钟静默窗口（点名位置）;IR004 无恢复事件=复盘没有终点（high）。缺 impact 事件直接拒绝（复盘必须有起点）。
- 边界：task_failure 解释任务为何挂,本 agent 复盘**事故是怎么被处理的**。
- CLI `incidentreview`（-f/--text/--llm/--fail-on-high gate）。
- 测试：`tests/test_incident_review.py` 11 项（指标/分级双档/乱序排序/ISO/混格式拒绝/缺 impact 拒绝/clean 场景/gate 双向）;页面 spec 2 项。
- 示例 `examples/incidentreview_demo/events.csv`（打中 IR001/002/003 三码）。

## 验证

```
tests\test_incidentreview_page.py ..                                     [100%]
============================== 2 passed in 8.02s ==============================

tests/test_incident_review.py + test_task_failure.py + test_registry.py
  + test_hub_pages.py + test_collision_guards.py
======================= 65 passed, 2 warnings in 14.91s =======================
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
