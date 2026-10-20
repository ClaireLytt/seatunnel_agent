# 05: 退役 Gradio 旧页

**What to build:** 按 react_migration.md 触点清单删 Gradio prompt_lab ui 模块及触点(hub/css.py 滚动标记、ui_testing/page.py READY/LABELS/选择器、catalog.py、test_registry.py 硬编码;report.py 的 _I18N 保留);全量验证;批次 2 报告。

**Blocked by:** 04(且用户过目截图批准后)

**Status:** ready-for-agent

- [ ] Gradio ui 模块及触点全部移除(report.py 后端渲染不动)
- [ ] 全量 ruff/mypy/pytest + uitest smoke 通过
- [ ] 批次 2 报告落盘 + check_workflow.py 通过
