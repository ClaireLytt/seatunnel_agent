# Agent 104 compact_plan — 小文件治理

日期: 2026-10-31 分支: fresh

## 内容

- 脚手架起步。`agents/data/compact_plan/`：planner（复用 sample_profile.parse_rows）、i18n、report、advisor_llm（可选执行评审）、api、tools、manifest（group governance, /compactplan）。
- 判定：小文件分区 = 均值低于阈值（默认 32MB）**且**文件数 >10——"小而少"的分区不动（测试钉住 dim.users 豁免）;合并候选按收敛文件数排名（合并后 = ceil(total_mb/目标 256MB)）,附 CONCATENATE / INSERT OVERWRITE 双模板。
- 分级：CP001 表级小文件占比（≥50% high、≥25% medium）;CP002 单分区 ≥1000 文件 = 独立的 NameNode 压力点（high）。
- 边界：partition_health 管分区**大小**,本 agent 管分区里的**文件数**（提案时已核对其检查面:断档/空分区/倾斜/缩水/暴涨）。
- CLI `compactplan`（-f/--text/--small-mb/--target-mb/--llm/--fail-on-high gate）。
- 测试：`tests/test_compact_plan.py` 10 项（排名/豁免/双码分级/阈值可调/gate 双向）;页面 spec 2 项。
- 示例 `examples/compactplan_demo/files.csv`（3802 文件可收敛 3758,千文件分区×2）。

## 验证

```
tests\test_compactplan_page.py ..                                        [100%]
============================== 2 passed in 7.76s ==============================

tests/test_compact_plan.py + test_partition_health.py + test_registry.py
  + test_hub_pages.py + test_collision_guards.py
======================= 64 passed, 2 warnings in 15.05s =======================
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
