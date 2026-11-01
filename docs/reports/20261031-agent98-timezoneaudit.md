# Agent 98 timezone_audit — 时间戳体检

日期: 2026-10-31 分支: fresh

## 内容

- 脚手架起步。`agents/data/timezone_audit/`：auditor（复用 sample_profile.parse_rows）、i18n、report、advisor_llm（可选接入侧归一方案）、api、tools、manifest（group quality, /timezoneaudit）。
- 列判定：列名时间形（ts/time/at/date/created/updated）或值 80% 可解析（ISO 或 10/13/16 位 epoch）;时间形列名即便解析率低也入列（只审能解析的值）。
- 四类发现：TZ001 同列显式时区不一致（+08:00 混 Z/naive,**直接证据**,high）;TZ002 epoch 秒/毫秒/微秒混用（聚合差千倍,high）;TZ003 小时分布双峰且相距 7..9 小时、两峰各 ≥20%（UTC/本地混用嫌疑,诚实标注为启发式,medium）;TZ004 1980..2100 之外的哨兵年份计数（medium）。
- 边界：dist_anomaly 管数值分布,本 agent 读时间戳**语义**;与 watermark_plan（乱序量级）互补。
- CLI `timezoneaudit`（-f/--text/--llm/--fail-on-high gate）。
- 测试：`tests/test_timezone_audit.py` 11 项（四码齐打/计数表/naive 混显式/一致列 clean/非时间列拒绝/时间形名低解析率豁免/gate 双向）;页面 spec 2 项。
- 示例 `examples/timezoneaudit_demo/rows.csv`（脚本生成:双时区双峰 + 秒毫秒混用 + 1970 哨兵）。

## 验证

```
tests\test_timezoneaudit_page.py ..                                      [100%]
============================== 2 passed in 8.47s ==============================

tests/test_timezone_audit.py + test_dist_anomaly.py + test_registry.py
  + test_hub_pages.py + test_collision_guards.py
======================= 67 passed, 2 warnings in 15.07s =======================
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
