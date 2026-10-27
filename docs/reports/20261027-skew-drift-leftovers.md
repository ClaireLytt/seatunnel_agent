# 批次结果报告:skew-drift-leftovers(2026-10-27)

## 批准依据

> 用户:"go on"(在票 03 报告列出两条遗留项并交付全部批次之后)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 漂移序列改为按(表,键)计算:同表多键的历史不再互相污染基线;compute_drift 增加 column 参数(缺省取最新测量的键) | agents/data/data_skew/drift.py | 本批次 |
| 高 | 调用方传入配置键:单配置尾行、目录巡检尾行(目录模式只打印"漂移"的表) | cli_cmds/skew.py | 本批次 |
| 高 | DriftCard 浏览器回归用例(真浏览器,种子历史→刷新→badge+delta);smoke 用例的折叠面板清单加入 Skew drift | tests/test_dataskew_page.py | 本批次 |
| 高 | 单测:按列分序列(region/id 混合历史)、目录巡检漂移尾行(稳定表静默) | tests/test_data_skew.py | 本批次 |

## 验证结果

```
ruff check src tests                        -> All checks passed!
mypy                                        -> Success: no issues found in 175 source files
pytest tests/test_data_skew.py -q           -> 193 passed in 7.39s
pytest -m uitest tests/test_dataskew_page.py -q
                                            -> 21 passed in 98.59s(真浏览器)
pytest -q(全量)                            -> 3496 passed, 1 skipped, 248 deselected, 2 warnings in 150.98s
python scripts/check_workflow.py            -> 提交后全 [PASS](见对话)
```

真浏览器证据:`pytest -m uitest tests/test_dataskew_page.py` 21 passed(含新用例 test_dataskew_drift_card)。

## 前后差异

- 测试类:test_data_skew.py 192 → 193;test_dataskew_page.py 20 → 21;全量 3495 → 3496 passed。
- 行为:修复一个真实缺陷——此前同表换键(或两配置读同表)时,漂移基线会混入另一把键的测量,结论失真;现在序列按键隔离。目录巡检尾部新增漂移行(仅漂移表,稳定/不足者静默)。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- uitest smoke 套件(YAML)未重跑:本批 UI 相关改动仅为 Playwright 测试文件与既有 DriftCard 的回归覆盖,页面代码未变;真浏览器验证由 `pytest -m uitest tests/test_dataskew_page.py`(21 passed)提供。
