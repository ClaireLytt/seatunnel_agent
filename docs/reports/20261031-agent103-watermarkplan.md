# Agent 103 watermark_plan — 水位线选型

日期: 2026-10-31 分支: fresh

## 内容

- 脚手架起步。`agents/data/watermark_plan/`：planner（复用 sample_profile.parse_rows）、i18n、report、advisor_llm（可选部署前评审）、api、tools、manifest（group build, /watermarkplan）。
- 输入：观测事件（event_time/arrival_time,HH:MM[:SS] 或 ISO,一次粘贴单格式——沿用 sla_board 教训）。
- 实测：乱序率（按到达序,事件时间倒挂占比）、迟到 p50/p95/p99/最大;**选型 = 常规 p99 × 1.25**（超一小时掉队者剔除——开发中实测抓到小样本 p99 退化成 max 的老问题:不剔除时 bound 被单个 2 小时掉队者顶到 9729s,剔除后 39s,回归测试钉住）;附残余比例、Flink SQL WATERMARK 子句与 forBoundedOutOfOrderness 片段。
- 分级：WM001 时钟漂移（到达早于事件,≥5% high）;WM002 重尾（max ≥ 常规 p99 的 10 倍,加大水位线只换延迟,走侧输出）;WM003 超一小时掉队者计数。
- 边界：rt_latency 管链路分段延迟,本 agent 管事件时间乱序的"设几秒"。"选型三部曲"收官（分区键/消息 Schema/水位线）。
- CLI `watermarkplan`（-f/--text/--llm/--fail-on-high gate）。
- 测试：`tests/test_watermark_plan.py` 10 项（bound 推导/掉队者剔除回归/漂移双档/紧凑流 clean/混格式拒绝/gate 双向）;页面 spec 2 项。
- 示例 `examples/watermarkplan_demo/events.csv`（乱序+漂移+掉队齐打）。

## 验证

```
tests\test_watermarkplan_page.py ..                                      [100%]
============================== 2 passed in 8.35s ==============================

tests/test_watermark_plan.py + test_rt_latency.py + test_registry.py
  + test_hub_pages.py + test_collision_guards.py
======================= 66 passed, 2 warnings in 14.98s =======================
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
