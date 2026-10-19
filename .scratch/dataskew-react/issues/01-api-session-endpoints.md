# 01: skew API 层 — 会话注册表 + 全部缺口端点

**What to build:** API 用户可以仅靠 REST 完成 Gradio 页的全部动作：llm/static
分析（含探针上下文）、连库（会话注册表）、探针验证、一致性实测、split-key
（含补丁 conf 文本）、运行时分析（事件日志 multipart + History Server）、
历史列表/载入、预设代理。现有 /check、/health 契约不变。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 会话注册表（datacompare 模式：X-Session-Id + TTL），connect/disconnect/status
- [ ] POST /analyze：mode static/llm，llm 不可用回退 static 并带 banner 字段；
      已连接会话自动带探针上下文
- [ ] POST /verify、POST /consistency：追加/替换 section 后的完整报告文本随响应返回
- [ ] POST /splitkey：多源检查 + 与历史前次对比 + 补丁 conf 文本（如适用）
- [ ] POST /runtime/eventlog（multipart）+ POST /runtime/history-server
- [ ] GET /history、POST /history/load；GET /presets、GET /presets/{name}
- [ ] 全部结构化错误；现有 /check /health 测试保持通过；新端点定向 API 测试
- [ ] ruff / mypy / pytest tests/test_data_skew.py 全绿
