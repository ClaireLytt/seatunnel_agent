# Web Task Agent React Migration

Labels: `ready-for-agent`
Branch: `plat`(用户要求:直接在 plat 开发提交,不切新分支)

## Problem Statement

Web Task Agent 页面(/webtask)仍是遗留 Gradio 实现;该模块刻意无 REST(api=None,驱动本机浏览器仅 CLI/UI),迁 React 必须补一条受控 HTTP 通路。另有既有 bug:页面默认 Start URL 为 hub 自身(127.0.0.1),但 run_task 未透传 allow_private,环回地址被 SSRF 守卫拒绝——默认参数点运行直接报错。

## Solution

把 Web Task 页 1:1 迁为独立 React workspace:任务目标、起始 URL、步数上限、运行 → 步骤流式显示 → 成功/失败报告。新增 SSE run 端点但默认关闭(`WEBTASK_API_ENABLED=1` 未设一律 403);顺带修复 allow_private 透传 bug(仅环回放行,私网仍拒)。验证通过后退役 Gradio 旧页。

## User Stories

1. As a platform user, I want the Web Task page rendered in React with the shared visual language, so that the product feels coherent
2. As an operator, I want a goal input describing the browser task, so that the agent knows what to do
3. As an operator, I want a start-URL input defaulting to the hub itself, so that driving the hub is one click away
4. As an operator, I want the default (loopback) start URL to actually work, so that the demo flow is not broken (pre-existing bug fix)
5. As an operator, I want a max-steps control (4–25, default 15), so that I bound the loop
6. As an operator, I want each agent step streamed into the report area as it happens, so that long runs show progress
7. As an operator, I want the final report (success/fail, steps, reply), so that I can review the outcome
8. As an operator, I want an empty goal caught locally with a localized notice, so that no request is wasted
9. As an operator, I want a clear notice when no LLM key is configured, so that I know to configure settings
10. As a platform operator, I want the run endpoint refused (403) unless WEBTASK_API_ENABLED=1 is set, so that the HTTP surface cannot drive the local browser by default
11. As a platform operator, I want non-loopback private URLs still rejected and allow_external/headed not exposed over HTTP, so that the SSRF/origin guards stay intact
12. As a Chinese-speaking user, I want en/zh copy to follow the st-lang cookie, so that language stays consistent
13. As a platform user, I want dark/light theme to follow the shared theme, so that the page matches the hub
14. As a platform operator, I want the page mounted via the manifest external-app convention, so that ui --build serves it like every workspace
15. As a developer, I want API + Playwright coverage for the migrated page, so that regressions are caught
16. As a developer, I want the Gradio page and its touchpoints removed after cutover, so that only one implementation remains

## Implementation Decisions

- 新建独立 workspace `frontend/web_task`(目录名 = manifest.name,route 仍 /webtask,vite base '/webtask/')
- 新增 api 模块:SSE run 端点(orchestrator/codefix 先例:worker thread + queue + StreamingResponse;事件 step ×N → done{WebTaskResult.to_dict 字段} 或 error{message})
- **安全门**:`WEBTASK_API_ENABLED` 未设为 "1" → 端点一律 403(默认等同无 REST);HTTP 面不暴露 allow_external/headed(固定 False);URL 校验沿用 validate_start_url
- **allow_private bug 修复(用户拍板 b 方案)**:run_task 增加 allow_private 透传参数(引擎一行级);UI/API 调用侧仅对环回地址(127.0.0.1/localhost/::1)计算放行,其余私网仍默认拒;SSRF 守卫本身不动
- React 页:左列 goal textarea + url 输入(默认 hub 自身)+ 步数 Slider(4–25 默认 15)+ 运行按钮;右列报告区——流式 step 行(step_line 文案)+ 终态报告(success/fail、reply、steps);空 goal 本地拦截(empty);403/错误 ⚠️ detail;无 key 由后端降级事件承载
- manifest:api= 挂新 router,external=True, render=""
- i18n:UI 字典(title/goal_label/goal_ph/url_label/steps_label/run_btn/report_ph/empty/no_key/step_line)平移 i18next;engine 工具描述硬编码不动
- 四票链:T1 端点+门+bug 修复(TDD)→ T2 React 页+manifest → T3 页测+截图+批次 1 报告 → T4 退役(用户过目批准后);T1–T3=批次 1
- UI 约束:禁蓝紫及渐变;manifest color #f97316(橙)合规不动

## Testing Decisions

- 只测外部行为;前端组件不做单测
- 缝 1(REST API):TestClient 覆盖——未设 WEBTASK_API_ENABLED 403、设 1 + FakeSession/ScriptedClient(tests/test_web_task.py 既有夹具)的 SSE step→done 序列、环回 URL 经修复后放行、非环回私网仍拒、无 key 降级事件;先例 codefix TestApi
- 缝 2(真浏览器):`tests/test_webtask_page.py`(uitest 标记,先例 test_codefix_page.py):en 冒烟、空 goal 本地提示且不发请求、未设开关时 403 内联显示(确定性,不起 Playwright 会话、不调 LLM)、en/zh 截图(before/after)
- 引擎层:allow_private 透传的单测补进 tests/test_web_task.py(环回经 run_task 放行、私网仍拒)
- 无 uitest yaml 退役,下限保持 29
- 验证命令:ruff/mypy/pytest、npm lint/build(web_task workspace)、uitest smoke --no-llm、check_workflow.py

## Out of Scope

- engine 工具集/SSRF 守卫/同源护栏改动(除 allow_private 透传);HTTP 暴露 allow_external/headed;运行历史持久化
- 其他页面迁移;main 操作、新分支、PR;前端组件单测

## Further Notes

- api=None 原为刻意安全决策;经用户确认(Q3)以 WEBTASK_API_ENABLED 默认关闭换取迁移
- allow_private 矛盾为探查发现的既有 bug(默认 URL 必败),经用户拍板 b 方案随票修复并记入报告
- 探查依据:manifest(api=None 注释)、engine.run_task 签名、session.validate_start_url/PlaywrightSession、ui.py do_run generator、tests/test_web_task.py、uitest 无用例
- 用户已在 grilling(Q1–Q5)确认全部决策
