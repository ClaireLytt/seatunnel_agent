# 01: lineage API 层 — 会话注册表 + 缺口端点 + SSE 问答

**What to build:** API 用户可以仅靠 REST 完成 Gradio 页全部动作：建图一次
（会话持图，返回 stats+表清单）后反复查询/搜索/路径/SLA（响应带链路
mermaid）/体检/快照（含 GET 列表）；自然语言问答可走 SSE 流式进度。
现有全部端点契约不变。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 会话注册表（skew 模式：cap+idle TTL），POST /session、POST /build
      （白名单前置 + 结构化错误 + stats/tables）
- [ ] 带 session 的 query/search/path/sla/health/snapshot/snapshot_diff/
      snapshots(GET) 薄包装（复用已建图；缺图 → 结构化 need_graph）
- [ ] SLA 响应补链路 mermaid（与旧 UI do_sla 等价）
- [ ] SSE 问答端点（EventCollector 事件 → step/tool_call/text_delta/done）
- [ ] 全部守卫结构化 {code,message}（后端 i18n）+ 通用异常兜底（不裸 500）
- [ ] 既有端点测试保持通过；新端点定向 API 测试（examples/lineage_demo）
- [ ] ruff / mypy / 相关 pytest 全绿
