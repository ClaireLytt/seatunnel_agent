# 批次结果报告:skew-runtime-label(2026-10-28)

## 批准依据

> 用户:"go on"(处理 skew-runtime-recheck 批次报告列出的遗留项)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 低 | eventlog 模式 label 并入 App ID(`name (application_xxx)`),同名应用的复测对比不再串基准;无 App ID 时行为不变 | agents/data/data_skew/runtime.py | 本批次 |
| 高 | 测试:带 App ID 的 eventlog label 断言 | tests/test_data_skew.py | 本批次 |

## 验证结果

```
ruff check src tests                 -> All checks passed!
mypy                                 -> Success: no issues found in 175 source files
pytest tests/test_data_skew.py -q    -> 199 passed in 7.08s
pytest -q(全量)                     -> 3503 passed, 1 skipped, 248 deselected, 2 warnings in 143.76s
python scripts/check_workflow.py     -> 提交后全 [PASS](见对话)
```

无 UI 改动,未跑 uitest。

## 前后差异

- 测试类:test_data_skew.py 198 → 199;全量 3502 → 3503 passed。
- 行为:event log 含 App ID 时诊断来源与复测基准按「应用名 (App ID)」区分;旧日志(无 App ID)与 History Server 模式不受影响。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- uitest:无 UI 改动,不要求。
