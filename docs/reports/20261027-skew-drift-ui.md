# 批次结果报告:skew-drift-ui(2026-10-27)

## 批准依据

> 用户:"把接下来所有批次都完成"(票 03 为剩余批次)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `GET /api/skew/drift`(只读,table 可选,复用 compute_drift/render_drift) | agents/data/data_skew/api.py | 本批次 |
| 高 | Data Skew 页漂移卡片:badge(漂移/稳定/暂无基线)+ 每指标 baseline→current(delta) | frontend/data_skew/src/components/DriftCard.tsx, App.tsx, api.ts | 本批次 |
| 中 | 前端 drf_* i18n(zh/en) | frontend/data_skew/src/i18n.ts | 本批次 |
| 高 | API 测试:单表 drift、全表 sweep + insufficient、空历史 | tests/test_data_skew.py | 本批次 |

## 验证结果

```
ruff check src tests                                        -> All checks passed!
mypy                                                        -> Success: no issues found in 175 source files
pytest tests/test_data_skew.py -q                           -> 192 passed in 7.37s
pytest -q(全量)                                            -> 3495 passed, 1 skipped, 247 deselected, 2 warnings in 153.30s
npm run lint --workspace data_skew                          -> eslint src(无错误)
npm run build --workspace data_skew                         -> built in 3.97s
python -m seatunnel_agent...ui_testing run --suite smoke --no-llm
                                                            -> PASS 16 · FAIL 0 · ERROR 0 · SKIP 0 · MANUAL 0 · 耗时 62s
python scripts/check_workflow.py                            -> 提交后全 [PASS](见对话)
```

真浏览器证据:runs/20261027_233930/report.html(smoke 16/16)。

## 前后差异

- 测试类:tests/test_data_skew.py 191 → 192 passed;全量 3494 → 3495 passed。
- UI 类:Data Skew 页侧栏新增"倾斜漂移"折叠卡(SplitKey 与 Runtime 之间);此前漂移仅 CLI 可见。截图/报告:runs/20261027_233930/report.html。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | smoke 套件无 drift 卡专项用例(卡片为新折叠面板,smoke 走既有路径) | tests/ui_testing YAML 无 drf 用例 | 用例计数与 YAML 对账约束,新增用例属扩面 | 卡片回归靠 API 测试 + eslint/build 保障 | 用户圈选后加 uitest 用例 |
| 低 | 目录巡检路径无漂移尾行(沿票 02 遗留) | cli_cmds/skew.py 目录分支 | 同票 02 报告 | 可用 skew-drift 代替 | 需要时再做 |

## 未执行的步骤

- 无。
