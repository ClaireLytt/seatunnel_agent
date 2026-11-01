# Agent 91 partition_plan — 分区键选型

日期: 2026-10-31 分支: fresh

## 内容

- 脚手架起步（`scripts/new_agent.py partition_plan --route /partitionplan ...`）。
- `agents/data/partition_plan/`：planner（复用 sample_profile.profile_rows + sqlglot WHERE 列解析）、i18n、report、advisor_llm（可选落 DDL 前评审）、api、tools、manifest（group build, /partitionplan）。
- 打分：WHERE 过滤频率×3 + 时间形加 2 分（date/datetime 类型或 dt/date/ts 命名）+ 基数甜区（2..5000 加 1,区外减 1）;结论四档理由点名（时间形且被过滤=经典键 / 只有一个值=分了等于没分 / 基数过高=撑爆元数据…）。
- 产出：`PARTITIONED BY (col)` 现成子句;高基数热过滤 *_id 列改配 `CLUSTERED BY ... INTO N BUCKETS`（N 按基数档位 8/32/64）。
- 发现：PP001 无合格时间形列（medium）;PP002 最热过滤列不适配分区键改分桶（medium）;PP003 不按任何采样列过滤的查询=裁不动的全扫（low,计数）。
- 边界：partition_health 体检已有分区,本 agent 为**还没分区**的表选键;按规则表在 PINS 补了两条邻居署名问法（partition_health 体检问法 + 本 agent 选键问法）,钉子全绿。
- CLI `partitionplan`（-f/--text/-q/--dialect/--llm/--fail-on-medium gate）。
- 测试：`tests/test_partition_plan.py` 11 项（推荐链路/单值与高基数不适配/分桶与 PP001+PP002 联动/PP003 计数/gate 双向）;页面 spec 2 项。
- 示例 `examples/partitionplan_demo/{sample.csv,queries.sql}`。

## 验证

```
tests\test_partitionplan_page.py ..                                      [100%]
============================== 2 passed in 9.28s ==============================

tests/test_partition_plan.py + test_partition_health.py + test_registry.py
  + test_hub_pages.py + test_collision_guards.py
======================= 65 passed, 2 warnings in 15.30s =======================
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
