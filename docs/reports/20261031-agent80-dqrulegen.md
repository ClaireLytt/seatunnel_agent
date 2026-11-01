# Agent 80 dq_rulegen — 质量规则草稿

日期: 2026-10-31 分支: fresh

## 内容

- `agents/data/dq_rulegen/`：generator（复用 sample_profile.profile_rows 列剖面,产出 data_quality 可直接加载的 rules.yaml）、i18n、report、advisor_llm（可选收紧建议,只发检查元数据）、api（make_text_router）、tools（MCP）、manifest（group quality, /dqrulegen）。
- 生成策略：row_count（min 1 + max_change_pct 护栏）;逐列 null_rate（观测空值率 + 5pp 余量,>50% 空的列整列跳过并说明）;100% 去重且主键形（整数或 *id*/*_no 名）列 → unique;低基数非数值列 → enum_domain 钉观测值集;非法标识符列跳过并提示改名。
- 回检守卫：生成前经 data_quality.parse_rules_text 加载,产出即可消费（contract_gen 同模式）。
- 定位闭环：sample_profile 报形状 → 本 agent 出规则 → data_quality 执行。
- CLI `dqrulegen`（-f/--text/-t/--where/--max-change-pct/--yaml-out 另存/--llm）。
- React 页面 `frontend/dq_rulegen/`：样例 + 表名 + 分区过滤 + LLM 复选框。
- 测试：`tests/test_dq_rulegen.py` 12 项（DQC 解析器真回检零错误、空洞列全跳过、余量计算、非法标识符跳过、yaml 另存）;`tests/test_dqrulegen_page.py` 双页面流。
- 示例 `examples/dqrulegen_demo/orders.csv`。

## 验证

```
tests\test_dqrulegen_page.py ..                                          [100%]
============================== 2 passed in 8.49s ==============================

tests/test_dq_rulegen.py + test_data_quality.py + test_registry.py + test_hub_pages.py
======================= 57 passed, 2 warnings in 13.62s =======================
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
