# 01: SSE run 端点 + WEBTASK_API_ENABLED 门 + allow_private 修复(TDD)

**What to build:** ① run_task 增加 allow_private 透传参数(默认 False,引擎一行级),补引擎单测(环回经 run_task 放行、非环回私网仍拒)。② 新建 api 模块:POST run,SSE step{tool,elapsed_ms,error} ×N → done{success,reply,steps,truncated,elapsed_ms} 或 error{message};`WEBTASK_API_ENABLED` != "1" → 403;HTTP 不暴露 allow_external/headed(固定 False);allow_private 由服务端按 URL 是否环回计算,不作为请求参数;无 key → error 降级事件。manifest api= 挂 router。TestClient 测试:403、FakeSession/ScriptedClient 的 SSE 序列、环回放行、私网仍 400/错误、无 key 降级。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] run_task(allow_private=...) 透传;引擎单测绿
- [ ] 未设开关 403;开关下 SSE step→done 序列正确(离线夹具)
- [ ] 环回 URL 放行、非环回私网仍拒;无 key 降级事件
- [ ] ruff/mypy/定向 pytest 通过
