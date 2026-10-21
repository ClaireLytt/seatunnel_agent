# 01: React 页完整实现 + manifest 切换

**What to build:** 打开 /docqa 是 React 页:多行问题输入(占位示例)、"用 LLM 作答"开关(默认关)、Ask 按钮 + Enter 提交 → running 提示 → Markdown 答案报告(含来源/摘录,来自 POST ask 的 markdown 字段);空问题本地显示 empty 文案不发请求;错误 ⚠️ detail;en/zh 文案平移 Gradio 字典,随 st-lang。manifest external=True, render="",api= 保留;workspace 目录 frontend/doc_qa(= manifest.name),vite base '/docqa/'。零新端点、引擎零改动。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] frontend/doc_qa workspace 建立并入 workspaces(对标 prompt_lab 骨架,无 recharts/motion)
- [ ] 输入/开关/Ask/Enter/running/报告/空问题拦截/错误显示可用
- [ ] manifest 切换完成,/docqa 路由不变
- [ ] npm lint + build、ruff/mypy、定向 pytest(test_doc_qa/test_registry/test_hub_pages)通过
