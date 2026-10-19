# 01: PII Scan React workspace + 全功能 + cutover

**What to build:** 用户在 `/pii` 用与其他 React 页一致的界面：SQL 目录
（demo 预填）+ 方言下拉 + "扫描目录"；"扫描粘贴的 SQL"折叠区；Markdown
敏感列报告；空输入/坏目录/异常本地化提示；zh/en 与暗色正确。旧 Gradio 页
退役，既有成功契约不变。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] before 截图（zh/en × 亮/暗）存 .scratch/pii-react/screenshots/
- [ ] API：bad_dir 结构化 {code,path}（白名单前置）+ scan 异常结构化降级
      {code:"scan_failed",error}；既有测试同步钉形状
- [ ] workspace frontend/pii_scan（schema_drift 参照）
- [ ] i18n 字典原样搬（弃用未使用的 result_label，注记）；方言/demo 预填钉定
- [ ] cutover：manifest external/render=""/api= 置空，hub 无条件挂 router，
      删 ui.py，_DATA_API_NAMES 移除 pii_scan
- [ ] `seatunnel-agent ui --build` 验证；after 截图（zh/en × 亮/暗 + 往返）
- [ ] ruff / mypy / 定向测试 / workspace lint+build 通过
