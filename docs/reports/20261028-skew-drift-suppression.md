# 批次结果报告:skew-drift-suppression(2026-10-28)

## 批准依据

> 用户:"go on"(对「drift 告警去重」提案的批准)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `notify_decision(prev, result)`:首报/重复静默/恶化升级(delta 变大或新增指标)/恢复通知 四态判定 | agents/data/data_skew/drift.py | 本批次 |
| 高 | `SkewHistory.last_drift(table)`;log_drift 记录 `deltas`(去重比较基准) | agents/data/data_skew/history.py | 本批次 |
| 高 | `skew-drift`:webhook 走去重,`--webhook-all` 逃生门,恢复卡(载荷 `recovered` 字段);`skew-splitkey` 两路径 webhook 漂移行同规则 | cli_cmds/skew.py | 本批次 |
| 中 | drf_recovered i18n(zh/en);指南补去重说明 | i18n.py, docs/data_skew_guide.md | 本批次 |
| 高 | 测试:notify_decision 单测(7 断言)+ CLI 端到端(首报/静默/逃生门/恶化重报/恢复卡) | tests/test_data_skew.py | 本批次 |

## 验证结果

```
ruff check src tests                 -> All checks passed!
mypy                                 -> Success: no issues found in 175 source files
pytest tests/test_data_skew.py -q    -> 201 passed in 10.07s
pytest -q(全量)                     -> 3505 passed, 1 skipped, 248 deselected, 2 warnings in 145.34s
python scripts/check_workflow.py     -> 提交后全 [PASS](见对话)
```

无 UI 改动,未跑 uitest。

## 前后差异

- 测试类:test_data_skew.py 199 → 201;全量 3503 → 3505 passed。
- 行为:此前漂移存在期间每次巡检重发同一告警(cron 日巡 = 每天一条重复消息);现在未恶化静默、恶化升级、恢复通知,控制台输出不受影响(照常打印)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | splitkey 路径不发恢复通知(仅 skew-drift 发) | cli_cmds/skew.py splitkey 尾部仅处理 drift verdict | splitkey 巡检只对 drift 落 mode=drift 记录,保持批次最小 | 经 splitkey 发现的漂移恢复后需跑一次 skew-drift 才出恢复卡 | 需要时补 |

## 未执行的步骤

- uitest:无 UI 改动,不要求。
