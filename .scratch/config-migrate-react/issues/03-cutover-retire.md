# 03: 切换 external 并退役 Gradio 页

**What to build:** manifest 改 external=True、render="";删 agents/data/config_migrate/ui.py;Python i18n 只删 UI-chrome key(report.py 后端渲染 key 保留);清理触点:hub/css.py 该页段、ui_testing/page.py 三处(READY 路由映射/LABELS/结果区选择器)、ui_testing/catalog.py AGENT_ROUTES/AGENT_LABELS(en/zh)、cases/*.yaml 中该页用例移除、tests/test_registry.py 与 test_ui_testing.py 相关断言更新。构建后 /migrate 由 React 静态页接管,未构建时提示页。

**Blocked by:** 01, 02

**Status:** ready-for-agent

- [ ] /migrate 由 React dist 接管(ui --build 后真浏览器可开)
- [ ] 旧 ui.py 删除,grep 无残留引用
- [ ] 触点清单逐条清理(对照 docs/react_migration.md 第 6-12 条)
- [ ] ruff/mypy + 受影响测试通过
