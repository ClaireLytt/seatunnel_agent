# Code Fix Agent React Migration

Labels: `ready-for-agent`
Branch: `plat`(用户要求:直接在 plat 开发提交,不切新分支)

## Problem Statement

Code Fix Agent 页面(/codefix,测试自愈 Agent)仍是遗留 Gradio 实现,与已迁 React 的页面不一致;且该模块刻意无 REST(api=None,改本地文件系统仅 CLI/UI),迁 React 必须补一条受控的 HTTP 通路。

## Solution

把 Code Fix 页 1:1 迁为独立 React workspace:目标路径、测试选择器、修复指令、步数上限、运行 → 步骤流式显示 → 成功/失败报告(diff/测试输出/worktree 路径)。新增的 run 端点带**强制目录白名单**(未配置一律 403,dagcheck 先例),引擎隔离机制不动。验证通过后退役 Gradio 旧页。

## User Stories

1. As a platform user, I want the Code Fix page rendered in React with the shared visual language, so that the product feels coherent
2. As a developer, I want to point the agent at a project path with failing tests, so that it attempts an automatic fix
3. As a developer, I want an optional pytest selector input, so that the agent targets the failing subset
4. As a developer, I want an optional instruction input, so that I can steer the fix
5. As a developer, I want a max-steps control (4–20, default 12), so that I bound the loop
6. As a developer, I want each agent step streamed into the report area as it happens, so that long runs show progress
7. As a developer, I want the final report (success/fail, steps, diff, final test output, worktree path), so that I can review before applying
8. As a developer, I want a clear notice when no LLM key is configured, so that I know to configure settings first
9. As a developer, I want empty-path submission caught locally with a localized notice, so that no request is wasted
10. As a platform operator, I want the run endpoint to refuse all requests unless an allowed-dirs whitelist is configured and the path falls inside it, so that the HTTP surface cannot touch arbitrary files
11. As a Chinese-speaking user, I want en/zh copy to follow the st-lang cookie, so that language stays consistent
12. As a platform user, I want dark/light theme to follow the shared theme, so that the page matches the hub
13. As a platform operator, I want the page mounted via the manifest external-app convention, so that ui --build serves it like every workspace
14. As a developer, I want API + Playwright coverage for the migrated page, so that regressions are caught
15. As a developer, I want the Gradio page and its touchpoints removed after cutover, so that only one implementation remains

## Implementation Decisions

- 新建独立 workspace `frontend/code_fix`(目录名 = manifest.name,route 仍 /codefix,vite base '/codefix/')
- 新增 api 模块:SSE run 端点(照 orchestrator chat 先例:worker thread + queue + StreamingResponse;事件 step ×N → done{result.to_dict 字段} 或 error{message});引擎 fix() 的 on_step 为现成钩子,engine/tools/report 零改动
- **安全门**:`CODEFIX_API_ALLOWED_DIRS`(os.pathsep 分隔)未配置 → 端点一律 403;请求 path resolve 后必须位于白名单目录之内,否则 403;in_place 参数不暴露(HTTP 面固定 worktree 隔离模式);无 LLM key → 降级事件(no_key 文案)而非 500
- manifest:api= 从 None 挂上新 router;external=True, render="";hub 无条件挂载先例适用
- React 页:左列 path/tests/instruction 输入 + 步数 Slider(4–20 默认 12)+ 运行按钮;右列报告区——流式 step 行逐条追加,终态渲染完整 Markdown 报告(ReportView);空 path 本地拦截(empty 文案);403/错误 ⚠️ 显示
- i18n:UI 字典(title/path_label/tests_label/tests_ph/inst_label/steps_label/run_btn/report_ph/empty/no_key/step_line)平移 i18next;report 模块后端渲染键(ok/fail/steps/diff/...)保留 Python 侧
- 四票链:T1 SSE 端点+白名单+API 测试 → T2 React 页完整+manifest 切换 → T3 页测+截图+批次 1 报告 → T4 退役(用户过目批准后);T1–T3=批次 1
- UI 约束:禁蓝紫及渐变;manifest color #e11d48 合规不动

## Testing Decisions

- 只测外部行为;前端组件不做单测
- 缝 1(REST API):TestClient 覆盖——未配置白名单 403、path 在白名单外 403、白名单内 + ScriptedClient 假 LLM 的 SSE 事件序列(step→done,success 真值由 run_pytest 复跑判定)、无 key 降级事件;先例 tests/test_orchestrator.py TestChatApi + tests/test_code_fix.py 的 ScriptedClient/红绿测试夹具
- 缝 2(真浏览器):`tests/test_codefix_page.py`(uitest 标记,先例 test_docqa_page.py):en 冒烟、空 path 本地提示且不发请求、白名单内真实小仓库的修复流(ScriptedClient 不可注入 HTTP 进程,改用无 key 降级路径或白名单 403 路径作确定性断言)、en/zh 截图(before/after)
- 无 uitest yaml 用例退役,下限保持 29
- 验证命令:ruff/mypy/pytest、npm lint/build(code_fix workspace)、uitest smoke --no-llm、check_workflow.py
- 不调真实 LLM

## Out of Scope

- engine/tools/report 引擎改动;HTTP 面暴露 in_place;CLI 行为变化
- 其他页面迁移;main 操作、新分支、PR;前端组件单测

## Further Notes

- api=None 原为刻意安全决策;本次经用户确认(grilling Q3)以强制白名单换取 React 迁移,默认(未配置 env)行为仍等同"无 REST"
- 探查依据:manifest(api=None 注释)、ui.py do_fix generator 流式、engine.fix 签名与 worktree 隔离、tools.py 路径守卫、tests/test_code_fix.py、uitest 无用例
- 用户已在 grilling(Q1–Q5)确认全部决策
