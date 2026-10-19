# 01: Config Lint React workspace + lint 全功能 + cutover 退役

**What to build:** 用户打开 `/conflint` 看到与其他 React 页同一设计语言的
Config Lint 页：粘贴 HOCON 配置点"Lint 配置"得到 Markdown 报告；展开
"目录批量 Lint"输入目录（默认示例目录）得到批量报告；空输入/坏目录给出
本地化提示；zh/en 切换与暗色模式全程正确。旧 Gradio 页随 cutover 退役，
路由与 REST 契约不变。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 迁移前截取 Gradio 版 before 截图（zh/en × 亮/暗）存入 spec 目录
- [ ] 新建 React workspace（目录名 = manifest.name），复用 @shared 主题/卡片/语言桥，加入 workspaces
- [ ] 单配置 lint 往返：输入 → 调既有 lint REST → 渲染 Markdown 报告；空输入提示与 Gradio 版对等
- [ ] 目录批量 lint 往返：折叠面板 + 默认示例目录；坏目录本地化错误与 Gradio 版对等
- [ ] i18n 字典原样搬入 i18next；暗色模式走共享主题
- [ ] cutover：manifest 切 external、删除 Gradio ui 模块；REST 挂载核对无双挂载
- [ ] `seatunnel-agent ui --build` 构建后页面可用，截取 after 截图（zh/en × 亮/暗）
- [ ] ruff / mypy / 定向测试通过；workspace lint + build 通过
