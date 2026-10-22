# 01: ci_inspect React workspace 与 cutover

**What to build:** 用户打开 `/ciinspect` 看到与其他已迁移 agent 页一致的 React 界面:粘贴 CI 日志→运行→Markdown 报告区,en/zh 双语与现有 i18n 机制一致;页面经 manifest external 挂载,纳入 `ui --build` 构建。旧 Gradio 代码本票不删(票 02)。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 新建 ci_inspect 前端 workspace,对标 issue_triage 骨架(vite base 为路由路径、@shared 组件/主题、api 走该 agent 现有 REST 暴露方式,若无则按先例最小新增文本入/报告出端点)
- [ ] i18n 词典从 Gradio ui.py 逐字平移,偏差注释说明
- [ ] manifest 改 `external=True`、`render=""`;workspace 目录名等于 manifest.name
- [ ] UI 遵守规范:无蓝紫渐变,与已迁移页视觉一致,不加多余解释文字
- [ ] i18n 单测(对标既有 test_<name>_i18n 模式)
- [ ] `npm run lint --workspace` + `npm run build --workspace` 通过;ruff/mypy/定向 pytest 通过
