# 02: D3 migrate — 8 个 api 切 sse_stream

**What to build:** code_fix/web_task/orchestrator/uitest/text2sql/data_lineage/data_comparison(compound)/seatunnel 删除本地 `_sse`+queue+thread+drain,换 common sse_stream;安全门/事件映射/done 载荷留各 router;SSE 对外契约零变化(既有 TestClient SSE 测试原样通过即验收);表达不了的变体(如 seatunnel 多会话 Conversation.queue)正当保留并汇报。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] `def _sse(` 在 src/ 仅剩 common 一处(正当保留者列出)
- [ ] 全部相关 API 测试回归绿;ruff/mypy 绿
