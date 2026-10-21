# 01: SSE run 端点 + 强制白名单(+ API 测试)

**What to build:** POST 发起修复,SSE 流式:step 事件 ×N → done{success,reply,steps,diff,workdir,final_test_output,truncated,elapsed_ms} 或 error{message}。安全门:`CODEFIX_API_ALLOWED_DIRS`(os.pathsep 分隔)未配置 → 403;path resolve 后不在任一白名单目录内 → 403;HTTP 面不暴露 in_place(固定 worktree 隔离);无 LLM key → 降级 done/error 事件(no_key 语义)而非 500。engine/tools/report 零改动;manifest api= 挂新 router。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 未配白名单 403;白名单外 path 403
- [ ] 白名单内 + ScriptedClient 假 LLM:SSE step→done 事件序列(红→绿修复用 test_code_fix.py 夹具)
- [ ] 无 key 降级事件(非 500)
- [ ] TestClient 测试覆盖上述;ruff/mypy/定向 pytest 通过
