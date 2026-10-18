# 01: Test Data Generator React workspace + 全功能 + cutover

**What to build:** 用户在 `/testgen` 用与其他 React 页一致的界面：预填
demo SQL、可选 DDL、方言下拉、行数滑杆（1-50）、SQLite 验证勾选、"生成"
按钮 → Markdown 报告；空 SQL 本地化提示；zh/en 与暗色正确。旧 Gradio 页
退役，REST 契约不变（后端零改动）。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] before 截图（zh/en × 亮/暗）存 .scratch/testgen-react/screenshots/
- [ ] workspace frontend/sql_testgen（sql_fmt 参照）：SQL（demo 预填）/DDL
      输入、方言下拉、行数滑杆、验证勾选、生成按钮、报告区
- [ ] 调 POST /generate（report=true），错误走结构化/文本 detail 展示
- [ ] i18n 字典原样搬 i18next；暗色走 @shared
- [ ] cutover：manifest external/render=""/api= 置空，hub 无条件挂 router，
      删 ui.py，_DATA_API_NAMES 移除 sql_testgen
- [ ] `seatunnel-agent ui --build` 验证；after 截图（zh/en × 亮/暗 + 往返）
- [ ] ruff / mypy / 定向测试 / workspace lint+build 通过
