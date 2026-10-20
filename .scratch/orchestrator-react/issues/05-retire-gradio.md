# 05: 退役 Gradio 旧页

**What to build:** 按 docs/react_migration.md 退役触点清单删除 Gradio orchestrator ui 模块及全部触点(hub/css、路由映射、catalog、registry 测试硬编码等),仓库内不再有两套实现。

**Blocked by:** 04(且用户过目截图批准后)

**Status:** ready-for-agent

- [ ] Gradio ui 模块及触点清单项全部移除
- [ ] 全量 ruff/mypy/pytest + uitest smoke 通过
- [ ] 批次 2 报告落盘 + check_workflow.py 通过
