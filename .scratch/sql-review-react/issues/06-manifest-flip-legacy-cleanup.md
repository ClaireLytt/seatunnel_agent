# 06: Manifest 切换 + 删旧页 + 收尾验证

**What to build:** /sqlreview 正式由 React 静态挂载提供（manifest external=True），未 build 时有占位提示页；旧 Gradio 页面、Python i18n 字典及死引用删除；全量验证通过并出批次报告。

**Blocked by:** 02, 03, 04, 05

**Status:** ready-for-agent

- [ ] manifest external=True，静态挂载 + 未 build 占位页
- [ ] 删除旧 Gradio ui 模块与 Python i18n 字典及死引用
- [ ] ruff / mypy / pytest / uitest 冒烟全部通过，截图前后对比
- [ ] 批次报告落盘 docs/reports/，check_workflow.py PASS
