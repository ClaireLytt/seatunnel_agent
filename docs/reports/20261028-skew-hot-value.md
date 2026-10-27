# 批次结果报告:skew-hot-value(2026-10-28)

## 批准依据

> 用户:"go on"(对「漂移报告带上热点值身份」提案的批准)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `log_splitkey`/`splitkey_metrics` 持久化 `top1_value`(截断 120 字符,旧记录向后兼容) | agents/data/data_skew/history.py, splitkey.py | 本批次 |
| 高 | `compute_drift` 跟踪热点值身份(最新 vs 基线期最近一次有值的测量);漂移时值变了则 `render_drift` 追加「热点值变了 {prev} → {cur}」行(四门面自动获得) | agents/data/data_skew/drift.py | 本批次 |
| 中 | drf_hot_changed i18n(zh/en) | agents/data/data_skew/i18n.py | 本批次 |
| 高 | 测试:同值涨幅无该行 / 换值出行(zh+en) / 旧记录无值兼容 / 稳定时值变但不出行;i18n 对账扩 key | tests/test_data_skew.py | 本批次 |

## 验证结果

```
ruff check src tests                 -> All checks passed!
mypy                                 -> Success: no issues found in 175 source files
pytest tests/test_data_skew.py -q    -> 206 passed in 9.99s
pytest -q(全量)                     -> 3510 passed, 1 skipped, 249 deselected, 2 warnings in 144.42s
python scripts/check_workflow.py     -> 提交后全 [PASS](见对话)
```

无 UI 代码改动(卡片经 text/REST 渲染自动获得),未跑 uitest。

## 前后差异

- 测试类:test_data_skew.py 202 → 206;全量 3509 → 3510 passed。
- 行为:漂移告警此前只有"占比 12%→28%";现在能区分**同一热点在变大**(老文案)与**热点换人**(新行:热点值变了 CN → US,提示先查上游数据)。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- uitest:无 UI 改动,不要求。
