# Ticket 02: Playwright 页测 + i18n parity + 触点清理

## 范围

1. **删 uitest 用例**：删除 `agents/devops/ui_testing/cases/conflint.yaml` 及散落引用；
   更新 `ui_testing/catalog.py` AGENT_ROUTES/LABELS、`ui_testing/page.py`
   （READY routes、LABELS、result selectors）中 conflint 相关条目。
2. **新建 Playwright 页测** `tests/test_conflint_page.py`（参照
   `tests/test_config_migrate_page.py`）：单配置 lint 往返、目录 lint 往返、
   坏目录警告、语言切换。
3. **i18n parity 测试**（参照 `tests/test_config_migrate_i18n.py`）：
   i18next zh/en 键齐全；后端 `config_lint/i18n.py` 只留报告渲染所需键，
   清除纯 UI chrome 键。
4. **清理触点**：`hub/css.py` 滚动标记（如有）、`tests/test_registry.py`
   `_DATA_API_NAMES`、`test_ui_testing.py` 中 conflint 硬编码；
   orchestrator `catalog.py:35` 路由映射保持 `/conflint` 不变（路由未改）。

## 验证

- ruff / mypy / 定向：`pytest tests/test_conflint_page.py tests/test_conflint_i18n.py tests/test_registry.py tests/test_ui_testing.py`
- 批次收尾（本票完成后由本会话统一执行）：全量 pytest、
  `python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm`、
  批次报告 `docs/reports/<YYYYMMDD>-conflint-react.md`、`python scripts/check_workflow.py`

## 不做

- 不动其他页面的用例与 i18n。
