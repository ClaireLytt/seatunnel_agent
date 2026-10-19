# 01: Metric Diff React workspace + 全功能 + cutover

**What to build:** 用户在 `/metricdiff` 用与其他 React 页一致的界面：
SQL 目录输入（demo 预填）、方言下拉、"检查口径"按钮 → 指标冲突 Markdown
报告；空目录/坏目录/异常本地化提示；zh/en 与暗色正确。旧 Gradio 页退役，
既有成功契约不变。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] before 截图（zh/en × 亮/暗）存 .scratch/metricdiff-react/screenshots/
- [ ] API：bad_dir 结构化 {code,path}（白名单前置）+ check 异常结构化降级
      {code:"check_failed",error}；既有测试同步；成功响应不变
- [ ] workspace frontend/metric_diff（schema_drift 参照）
- [ ] i18n 字典原样搬；方言列表与 demo 预填 parity 钉定
- [ ] cutover：manifest external/render=""/api= 置空，hub 无条件挂 router，
      删 ui.py，_DATA_API_NAMES 移除 metric_diff
- [ ] `seatunnel-agent ui --build` 验证；after 截图（zh/en × 亮/暗 + 往返）
- [ ] ruff / mypy / 定向测试 / workspace lint+build 通过
