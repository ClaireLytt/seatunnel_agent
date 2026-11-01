# /code-simplification — 本会话新增代码简化扫描

日期: 2026-10-31 分支: fresh

## 范围与结论

范围 = 本会话新增的 agent 代码（精准修改原则）。扫描后落地 4 处行为零变化
的简化,每处单独改单独测;另有 1 处提取候选经权衡**主动放弃**并记录理由。

## 落地的简化

1. compact_plan/report.py — 无效三元（`f.value if code=="CP002" else
   f.value` 两支相同）收敛为直接传值。
2. avro2ddl/converter.py — `f.get("type")` 三连取值收敛为局部变量
   `avro_type`,正逻辑在前的 isinstance 分支。
3. timezone_audit/auditor.py — hits 列表不再携带从未使用的原始值 v,
   循环解包从 `for _, (kind, dt)` 简化为 `for kind, dt`。
4. mock_data/generator.py — 序列发号的"先加一再减一"写法改为
   start/value/next 三步直叙。

## 放弃的候选（Chesterton's Fence / Balance）

- sla_board、incident_review、watermark_plan 三处时间解析器形状相似,
  但格式规则不同（sla/incident 只收 HH:MM,watermark 收 HH:MM:SS;
  量纲分别为分钟与秒）。提取公共件需要加 allow_seconds/量纲参数,
  且会悄改 sla_board 对 HH:MM:SS 的拒绝行为——提取后的接口比三个
  12 行的本地函数更复杂,判定为不值得,保留现状并在此记录。

## 验证

```
每处改动后单测:10 + 11 + 11 + 12 passed
合并复跑:
============================= 44 passed in 6.27s ==============================
All checks passed!   (ruff)
全量回归(本批前台台账):
=== 4653 passed, 1 skipped, 404 deselected, 3 warnings in 177.26s ===
```

## Gate

```
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```
