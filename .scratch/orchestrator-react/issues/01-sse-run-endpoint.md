# 01: 后端流式 run 端点(SSE)+ API 测试

**What to build:** 客户端向 orchestrator API 发起一次 run,能逐条收到步骤事件(每个工具调用一条),最后收到最终回答事件。TestClient 测试验证事件序列与最终答案。若现有 run 端点已满足流式契约,则本票收敛为补测试+确认契约。不修改 engine/router/catalog 编排逻辑。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] SSE(或等价流式)run 端点存在且事件粒度 = 每个工具调用一条步骤消息 + 最终回答
- [ ] 会话 id 贯穿:同 session 连续 run 共享上下文;支持前端会话恢复所需的查询接口
- [ ] pytest(TestClient)覆盖:事件序列、最终回答、agents 列表
- [ ] ruff/mypy/定向 pytest 通过
