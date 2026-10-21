# 05: 退役 Gradio 旧页

**What to build:** 删 Gradio llm_cost ui 模块(含 matplotlib _cost_figure/_tokens_figure 与 tempfile CSV)及触点(catalog.py、test_registry.py 等;i18n.py 的 rpt_* 后端键保留);顺手更正 docs/react_migration.md 过时的 "api= 留空" 表述(以 hub 无条件挂载 + 保留 api= 的现行约定为准);全量验证;批次 2 报告。

**Blocked by:** 04(且用户过目截图批准后)

**Status:** ready-for-agent

- [ ] Gradio ui 模块及触点全部移除(后端 i18n rpt_* 保留)
- [ ] react_migration.md api= 表述更正
- [ ] 全量 ruff/mypy/pytest + uitest smoke 通过
- [ ] 批次 2 报告落盘 + check_workflow.py 通过
