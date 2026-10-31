# Agent 62 cost_allocation — 成本分摊

日期: 2026-10-31 分支: fresh

## 内容

- `agents/data/cost_allocation/`：allocator（复用 sample_profile.parse_rows）、i18n、report、advisor_llm（可选账单通报）、api（make_text_router）、tools（MCP）、manifest（group governance, /costalloc）。
- 输入：用量清单（owner/item/storage_gb/compute_hours,owner 空计入"无主"）+ 存储/计算单价。
- 账单：逐归属方 存储/计算/合计/占比 + 各家成本大头 TOP3,大头在前;确定性（同清单同单价同账单,有测试钉住）。
- 分级：CA001 无主开销占比（≥30% high、≥10% medium）——没人优化无主成本;CA002 单家 ≥50% 集中度提示（low,无主不计入该项）。
- 边界：storage_cost 定价"持有什么"、retention_policy 决定"留什么",本 agent 回答"谁来付";可归档清单从 retention 直接喂入。
- CLI `costalloc`（-f/--text/--storage-price/--compute-price/--llm/--fail-on-high CI gate）。
- React 页面 `frontend/cost_allocation/`：清单 + 双单价 + LLM 复选框,演示预填含 16% 无主开销。
- 测试：`tests/test_cost_allocation.py` 10 项（账单数值/无主分级双档/集中度含 50% 边界/确定性/gate 双向）;页面测试 standard_page_tests 工厂 spec。
- 示例 `examples/costalloc_demo/usage.csv`。

## 验证

```
tests\test_costalloc_page.py ..                                          [100%]
============================= 2 passed in 10.64s ==============================

tests/test_cost_allocation.py + test_registry.py + test_hub_pages.py + test_collision_guards.py
======================= 47 passed, 2 warnings in 14.41s =======================
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
