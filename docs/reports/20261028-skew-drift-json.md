# 批次结果报告:skew-drift-json(2026-10-28)

## 批准依据

> 用户:"go on"(对「skew-drift -F json 机器可读输出」提案的批准;动手前已同步 origin/main 进 skew)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `drift_item_dict` 单一真理源:REST `/api/skew/drift` 改为复用,消除与 CLI 的形状漂移风险 | agents/data/data_skew/drift.py, api.py | 本批次 |
| 高 | `skew-drift --format/-F text|json`:json 输出 `{"items":[...]}` 与 REST 同形(恢复项带 `recovered: true`),静默 rich 装饰;`--fail`/webhook/`-o`/落历史语义不变;空历史输出空列表 | cli_cmds/skew.py | 本批次 |
| 高 | 测试:json 可解析+字段断言+hot_value、--fail 退出码、空历史;顺手修正 _seed_drift_history 未透传 top1_value 的测试助手缺口 | tests/test_data_skew.py | 本批次 |

## 验证结果

```
ruff check src tests                 -> All checks passed!
mypy                                 -> Success: no issues found in 175 source files
pytest tests/test_data_skew.py -q    -> 212 passed in 10.60s
pytest -q(全量)                     -> 3517 passed, 1 skipped, 249 deselected, 2 warnings in 148.09s
python scripts/check_workflow.py     -> 提交后全 [PASS](见对话)
```

无 UI 改动,未跑 uitest。

## 前后差异

- 测试类:test_data_skew.py 211 → 212;全量 3516 → 3517 passed。
- 行为:流水线此前只能爬 rich 文本屏;现在 `skew-drift -F json --fail` 一步产出与 REST 同形的结构化结果 + 门禁退出码。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- uitest:无 UI 改动,不要求。
