# 01: Schema Drift React workspace + 全功能 + cutover

**What to build:** 用户在 `/schemadrift` 用与其他 React 页一致的界面：
方言下拉、旧/新 DDL 双输入、"对比"按钮 → Markdown 漂移报告；目录折叠区
（demo 预填）→ 目录级报告；空输入/半填/坏路径本地化提示；zh/en 与暗色
正确。旧 Gradio 页退役，既有成功契约不变。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] before 截图（zh/en × 亮/暗）存 .scratch/schemadrift-react/screenshots/
- [ ] API：bad_path 对齐结构化 {code,path}（白名单前置已有）;
      既有测试同步断言;成功响应字段不变
- [ ] workspace frontend/schema_drift（sql_fmt 参照）：方言下拉、双 DDL
      输入、目录折叠区（demo 预填）、ReportView
- [ ] i18n 字典原样搬 i18next；方言列表 parity 钉定
- [ ] cutover：manifest external/render=""/api= 置空，hub 无条件挂 router，
      删 ui.py，_DATA_API_NAMES 移除 schema_drift
- [ ] `seatunnel-agent ui --build` 验证；after 截图（zh/en × 亮/暗 + 往返）
- [ ] ruff / mypy / 定向测试 / workspace lint+build 通过
