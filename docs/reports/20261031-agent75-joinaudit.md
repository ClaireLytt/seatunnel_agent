# Agent 75 join_audit — 关联质量审计

日期: 2026-10-31 分支: fresh

## 内容

- `agents/data/join_audit/`：auditor（复用 sample_profile.parse_rows）、i18n、report、advisor_llm（可选关联评审,只发指标不发数据行）、api（make_text_router）、tools（MCP）、manifest（group quality, /joinaudit）。
- 键语法：同名 `k`、异名 `lk=rk`、逗号组合多键;空键行单独计数。
- 指标与分级：两侧匹配率（<90% medium、<50% high）→ JA002/JA003 含孤儿键样例;JA001 多对多键（两侧均重复）= high,给出行数爆炸系数与最严重键（lcount×rcount TOP5）;JA004 空关联键占比（≥1% medium）。1:N 不算多对多（测试覆盖）。
- 边界：data_comparison 比同构表内容,rt_offline_diff 比实时离线口径;本 agent 审计 JOIN 本身。
- CLI `joinaudit`（-l/-r/-k/--llm/--fail-on-high CI gate）。
- React 页面 `frontend/join_audit/`：双数据输入 + 键输入 + LLM 复选框,演示预填含多对多/孤儿/空键案例。
- 测试：`tests/test_join_audit.py` 12 项;`tests/test_joinaudit_page.py` 双页面流。
- 示例 `examples/joinaudit_demo/{orders,user_tags}.csv`。

## 验证

```
tests\test_joinaudit_page.py ..                                          [100%]
============================== 2 passed in 7.57s ==============================

tests/test_join_audit.py + test_registry.py + test_hub_pages.py
======================= 47 passed, 2 warnings in 13.16s =======================
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
