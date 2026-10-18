# 03: React 页 B — 搜索/路径/SLA/体检/快照 + SSE 问答 + cutover

**What to build:** 用户在 React 页完成其余功能：表名模糊搜索、两表路径、
SLA 延迟影响（小时输入 + 链路图）、治理体检、快照保存/列表/对比、
自然语言问答（SSE 流式进度 + 回答 + 可能的新图）。完成后 cutover：
manifest 切 external、删 Gradio ui.py、hub 无条件挂 router、
_DATA_API_NAMES 移除，`ui --build` 验证并截 after 图；/impact 页不受影响。

**Blocked by:** 02 (React 页 A)

**Status:** ready-for-agent

- [ ] 搜索区 + 高级区（路径终点下拉、SLA 小时数、体检按钮）
- [ ] 快照区（命名保存、列表下拉刷新、对比）
- [ ] 问答折叠区：SSE 进度渲染（phase/tool/text 增量）+ 回答 + 新图替换
- [ ] cutover 全套（含 ui.py 删除后 /impact 仍可渲染的验证）
- [ ] after 截图（zh/en × 亮/暗 + 查询往返）
- [ ] ruff / mypy / 定向测试 / workspace lint+build 通过
