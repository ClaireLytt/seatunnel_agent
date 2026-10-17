# 01: React 骨架 + 最小 Review 闭环

**What to build:** 用户访问 /sqlreview 看到 React 版页面（engineering-paper 主题、badge 头部"data / sqlreview"、Home 链接），粘贴 SQL、选方言、选 static/LLM 模式，点 Review 后看到 markdown 格式的审查报告（带 loading 态）。页面走现有 REST `/review` 端点，router 无条件挂载。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] frontend/sql_review workspace 建立并可 build（Vite base /sqlreview/，共享主题/tailwind preset）
- [ ] sql_review router 无条件挂载（不依赖 --api）
- [ ] static 模式 review 端到端跑通并渲染报告
- [ ] Playwright 冒烟：页面加载 + static review 闭环
