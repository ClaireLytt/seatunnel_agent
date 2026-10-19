# 03: React 页 B — 连接/探针/一致性/split-key/runtime + cutover

**What to build:** 用户在 React 页完成全部实测功能：连接数据源折叠区
（预设读取、`st_dataskew_conn` cookie 预填、采样比例、连接/验证倾斜/
一致性实测按钮与状态行）、SeaTunnel split-key 折叠区（粘贴/上传 conf、
补丁 conf Blob 下载）、运行时折叠区（事件日志上传 + History Server）。
完成后 cutover：manifest 切 external、删 Gradio ui.py、hub 无条件挂
router、_DATA_API_NAMES 移除，`ui --build` 验证并截 after 图。

**Blocked by:** 02 (React 页 A)

**Status:** ready-for-agent

- [ ] 连接折叠区全功能（sqlite 特例、空 host 走环境配置、密码框 type=password）
- [ ] 探针验证/一致性：响应完整报告文本直接替换渲染；未连接/无优化 SQL 提示对等
- [ ] split-key 折叠区 + 补丁 conf Blob 下载（仅最佳 key 不同时出现）
- [ ] runtime 折叠区：事件日志 multipart 上传 + History Server URL/app id
- [ ] cookie `st_dataskew_conn` 预填表单并展开折叠区（无密码）
- [ ] cutover 全套 + `seatunnel-agent ui --build` 页面可用 + after 截图
- [ ] ruff / mypy / 定向测试 / workspace lint+build 通过
