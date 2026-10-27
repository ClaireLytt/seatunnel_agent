# 批次结果报告:skew-drift-cli(2026-10-27)

## 批准依据

> 用户:"go on"(票 01 完成报告中已声明"下一个 frontier 是票 02(`skew-drift` CLI + splitkey 尾行 + webhook),我继续"后的批准)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `skew-drift [TABLE]` CLI:单表/全表巡检,drift 落历史(mode=drift),`--webhook` 漂移时推送 | src/seatunnel_agent/cli_cmds/skew.py | 本批次 |
| 高 | `skew-splitkey` 单配置报告尾部追加漂移行(与基线对比) | src/seatunnel_agent/cli_cmds/skew.py | 本批次 |
| 高 | `render_drift` 共享渲染 + `SkewHistory.log_drift` | agents/data/data_skew/drift.py, history.py | 本批次 |
| 中 | drf_* i18n 字符串(zh/en 对) | agents/data/data_skew/i18n.py | 本批次 |
| 高 | 6 个新测试:单表输出+历史落盘、全表+insufficient、空历史、webhook payload、i18n 对账、splitkey 尾行(mock executor,3 次复跑) | tests/test_data_skew.py | 本批次 |

## 验证结果

```
ruff check src tests                      -> All checks passed!
mypy                                      -> Success: no issues found in 175 source files
pytest tests/test_data_skew.py -q         -> 191 passed in 10.32s
pytest -q(全量)                          -> 3494 passed, 1 skipped, 247 deselected, 2 warnings in 160.50s
python scripts/check_workflow.py          -> 提交后全 [PASS](见对话)
```

无 UI 改动,未跑 uitest。

## 前后差异

- 测试类:tests/test_data_skew.py 185 → 191 passed(+6);全量 3488 → 3494 passed。
- 行为:此前 `skew-splitkey` 只与"上一次"比较(spk_recheck_drift);现在额外给出对历史基线(中位数)的漂移判定,且可离线 `skew-drift` 巡检全部有历史的表并推 webhook。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | 前端/REST 尚无 drift 展示 | frontend/data_skew 无调用 | 拆票串行 | 网页用户看不到漂移 | 票 03 |
| 低 | 目录巡检(--conf 为目录)路径未加漂移尾行 | cli_cmds/skew.py 目录分支 | 保持批次最小;目录模式输出为汇总表,逐表漂移行会刷屏 | 目录巡检需另跑 skew-drift | 如需,票 03 后评估 |

## 未执行的步骤

- uitest:本批次无 UI 改动,按第 8 节规则不要求。
