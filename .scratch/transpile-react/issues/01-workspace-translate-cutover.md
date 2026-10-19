# 01: SQL Transpile React workspace + 全功能 + API 补齐 + cutover

**What to build:** 用户在 `/transpile` 用与其他 React 页一致的界面完成：
选方言对（源含 Auto detect）翻译 SQL，右侧复制按钮代码块 + 报告；批量翻译
目录（可选写出目录，白名单内）；翻译后可生成 LLM 建议（无 key/无建议项
本地化说明）；sql_review 送来的 SQL 自动预填；空输入/坏目录本地化提示；
zh/en 与暗色正确。旧 Gradio 页退役，既有 REST 契约不变。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] before 截图（zh/en × 亮/暗）存 .scratch/transpile-react/screenshots/
- [ ] API：POST /advice 薄包装（结构化 no_key/none 状态）；/batch 可选 out_dir
      （读写目录同白名单）；带定向 API 测试；既有契约测试保持通过
- [ ] workspace frontend/sql_transpile：双栏布局、方言对下拉（GET /dialects）、
      译文代码块（ConfView 先例）、批量折叠区（目录+输出目录）、建议折叠区、
      localStorage 桥 pickup
- [ ] i18n 字典原样搬 i18next；暗色走 @shared
- [ ] cutover：manifest external/render=""/api= 置空，hub 无条件挂 router，
      删 ui.py，_DATA_API_NAMES 移除 sql_transpile
- [ ] `seatunnel-agent ui --build` 验证页面；after 截图（zh/en × 亮/暗 + 往返）
- [ ] ruff / mypy / 定向测试 / workspace lint+build 通过
