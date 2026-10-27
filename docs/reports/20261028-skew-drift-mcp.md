# 批次结果报告:skew-drift-mcp(2026-10-28)

## 批准依据

> 用户:"go on"(遗留清零后继续 issue #21 线;按 CLAUDE.md 持续开发,本批为门面对齐)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | MCP 工具 `skew_drift`(table/column/lang 可选,只读历史,巡检落历史 source=mcp);纳入 no-db 档(不连库) | agents/data/data_skew/mcp_server.py | 本批次 |
| 中 | 统一工具箱 /mcp 页 zh+en 描述 | agents/data/mcp_toolbox/ui.py | 本批次 |
| 高 | 测试:MCP drift 行为(空历史指引/单表/sweep/落历史/no-db 档);工具集合与计数断言更新 | tests/test_data_skew.py, tests/test_mcp_toolbox.py | 本批次 |

## 验证结果

```
ruff check src tests                             -> All checks passed!
mypy                                             -> Success: no issues found in 175 source files
pytest tests/test_mcp_toolbox.py tests/test_data_skew.py -q
                                                 -> 225 passed, 2 warnings in 17.38s
pytest -q(全量)                                 -> 3497 passed, 1 skipped, 248 deselected, 2 warnings in 155.82s
python scripts/check_workflow.py                 -> 提交后全 [PASS](见对话)
```

无 UI 代码改动(/mcp 页仅新增描述文案),未跑 uitest。

## 前后差异

- 测试类:全量 3496 → 3497 passed(+1 MCP drift 用例;另两处既有断言随工具数 8→9 更新)。
- 行为:drift 此前只有 CLI/REST/前端入口;现在 MCP 客户端(含统一工具箱,含 no-db 档)可直接调用,四个门面对齐。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- uitest:无页面逻辑改动,不要求。
