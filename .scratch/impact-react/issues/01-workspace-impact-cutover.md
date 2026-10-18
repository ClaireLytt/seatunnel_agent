# 01: Change Impact React workspace + 全功能 + API 补齐 + cutover

**What to build:** 用户在 `/impact` 用与其他 React 页一致的界面：双页签
（目录模式 / 粘贴 SQL + 可选上下文目录）、共享方言下拉与深度滑杆、分析后
得到严重度着色 Mermaid 图 + 分级 Markdown 报告（粘贴模式附 SQL diff）；
缺输入/坏目录本地化提示；zh/en 与暗色正确。旧 Gradio 页退役，lineage 包
不再有 Gradio 残留。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] before 截图（zh/en × 亮/暗）存 .scratch/impact-react/screenshots/
- [ ] API：/impact 响应加 mermaid（恒有）与 sql_diff（text 模式）;
      白名单前置 + 结构化 bad_dir；既有字段与测试不变；新增可加字段断言
- [ ] workspace frontend/change_impact（data_lineage 参照，GraphView 复制
      去 onNode）：双页签、dialect/depth、分析按钮 ×2、图+报告区
- [ ] i18n 字典原样搬 i18next；暗色 mermaid 随主题
- [ ] cutover：manifest 切 external、删 ui_impact.py 与 render.py 的
      mermaid_html/_MERMAID_HTML_TEMPLATE（__init__ 导出与相关单测同步处理）
- [ ] `seatunnel-agent ui --build` 验证；after 截图（zh/en × 亮/暗 + 往返）
- [ ] ruff / mypy / 定向测试 / workspace lint+build 通过
