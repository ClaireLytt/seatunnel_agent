# 02: 批量目录迁移路径

**What to build:** API 批量端点(任务目录+输出目录,复用 migrator.migrate_dir 与批量报告渲染,保留服务器路径语义);页面加"批量迁移目录"折叠区(两个路径输入 + Batch migrate 按钮),展示批量结果报告(成功/失败清单)。与现 Gradio 行为 1:1。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] API 批量端点 pytest 覆盖成功与部分失败
- [ ] 页面批量表单提交并展示批量报告
- [ ] i18n 文案齐备
- [ ] ruff/mypy + 定向测试通过
