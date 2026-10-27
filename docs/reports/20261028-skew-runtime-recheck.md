# 批次结果报告:skew-runtime-recheck(2026-10-28)

## 批准依据

> 用户:"go on"(drift 线闭环后继续 issue #21;方向为此前预告的"runtime 诊断与 drift/复测的衔接")。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 运行时复测对比:同一应用再次诊断时,报告尾部给出「上次诊断 N → 本次 M——好转/恶化/无变化」 | agents/data/data_skew/runtime.py(diagnose_and_log) | 本批次 |
| 高 | `SkewHistory.last_runtime(app)`(与 last_splitkey 同型) | agents/data/data_skew/history.py | 本批次 |
| 高 | 收敛重复:CLI/REST/MCP×2 四处"计数+落历史+渲染"重复块统一走 diagnose_and_log | cli_cmds/skew.py, data_skew/api.py, data_skew/mcp_server.py | 本批次 |
| 中 | rt_recheck_* i18n(zh/en 三态) | agents/data/data_skew/i18n.py | 本批次 |
| 高 | 测试:last_runtime 单测、i18n 对账、CLI 首测无对比行/复测出"无变化"行 | tests/test_data_skew.py | 本批次 |

## 验证结果

```
ruff check src tests                 -> All checks passed!
mypy                                 -> Success: no issues found in 175 source files
pytest tests/test_data_skew.py -q    -> 198 passed in 12.31s
pytest -q(全量)                     -> 3502 passed, 1 skipped, 248 deselected, 2 warnings in 147.20s
python scripts/check_workflow.py     -> 提交后全 [PASS](见对话)
```

无 UI 代码改动(REST 返回的 section 文本自然带上对比行,前端 Markdown 直接展示),未跑 uitest。

## 前后差异

- 测试类:test_data_skew.py 196 → 198;全量 3500 → 3502 passed。
- 行为:此前运行时诊断每次孤立;现在同一应用(按 label)复测会对比上次确认倾斜 stage 数,闭环"调参→重跑→看是否好转"。四个入口(CLI/REST/MCP eventlog/MCP history-server)行为一致且共享同一实现。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | eventlog 模式 label 为 app 名,同名不同应用会串(History Server 模式用 app_id,无此问题) | runtime.py parse_eventlog label | label 即日志内 app name | 同名应用复测对比可能对错基准 | 需要时在 label 中并入 applicationId |

## 未执行的步骤

- uitest:无 UI 改动,不要求。
