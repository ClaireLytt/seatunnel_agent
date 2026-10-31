# Agent 81 retention_policy — 生命周期建议

日期: 2026-10-31 分支: fresh

## 内容

- `agents/data/retention_policy/`：advisor（复用 sample_profile.parse_rows）、i18n、report、advisor_llm（可选清理提案）、api（make_text_router）、tools（MCP）、manifest（group governance, /retention）。
- 输入：分区清单（table/partition/size_gb/last_access）,分区值 dt=YYYY-MM-DD/YYYYMMDD 可解析;解析不出日期的分区跳过并计 RP003。
- 算法：基准日取数据内最新日期（同清单必得同建议,确定性）;TTL = 活跃窗口（默认 90 天）内仍被读的最老分区年龄 + 30 天余量,按 30 天向上取整,下限 30;超 TTL 且不活跃的分区 → 可归档（累计释放 GB）,其中从未被读的 → 可清理。
- 分级：RP001 冷数据占比（≥50% high、≥25% medium）;RP002 从未被读分区（medium）;RP003 日期盲区（low）。最冷表在前。
- 边界：storage_cost 定价"现在持有什么",本 agent 决定"往后留什么";可归档/清理清单直接喂 62 cost_allocation 与 69 offboard_plan。
- CLI `retention`（-f/--text/--active-days/--llm/--fail-on-high CI gate）。
- React 页面 `frontend/retention_policy/`：清单输入 + 活跃窗口 + LLM 复选框。
- 测试：`tests/test_retention_policy.py` 11 项（确定性/TTL 推导/归档 vs 清理区分/日期盲区/gate）;页面测试 standard_page_tests 工厂 spec。
- 示例 `examples/retention_demo/partitions.csv`（三张表三种形态:高冷占比/中等/全活跃）。

## 验证

```
tests\test_retention_page.py ..                                          [100%]
============================== 2 passed in 7.79s ==============================

tests/test_retention_policy.py + test_registry.py + test_hub_pages.py + test_collision_guards.py
======================= 48 passed, 2 warnings in 14.34s =======================
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
