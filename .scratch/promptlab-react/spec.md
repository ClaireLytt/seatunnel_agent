# Prompt Lab React Migration

Labels: `ready-for-agent`
Branch: `plat`(用户要求:直接在 plat 开发提交,不切新分支)

## Problem Statement

Prompt Lab 页面(/promptlab)仍是遗留 Gradio 实现,与已迁 React 的各 agent 页(含本轮 orchestrator、llm_eval)视觉与技术栈不一致,维护两套 UI 栈成本高。

## Solution

按既有迁移先例把 Prompt Lab 1:1 迁为独立 React workspace:prompt/system 输入、profile 多选(默认 "(active)")、parallel 开关(默认开)、运行矩阵对比、Markdown 报告、成功 cell 两两 Diff、实验历史。复用 @shared 与 engineering-paper 主题;验证通过后退役 Gradio 旧页。不加新功能。

## User Stories

1. As a platform user, I want the Prompt Lab page rendered in React with the shared visual language, so that the product feels coherent
2. As a prompt engineer, I want prompt and system inputs, so that I can define the experiment
3. As a prompt engineer, I want to pick multiple provider profiles with "(active)" preselected, so that I compare models side by side
4. As a prompt engineer, I want a parallel toggle (default on), so that big matrices finish fast
5. As a prompt engineer, I want a running indicator during the matrix run, so that I know it is in flight
6. As a prompt engineer, I want the matrix result as a Markdown report (per-cell reply/latency/tokens/errors), so that I compare outputs at a glance
7. As a prompt engineer, I want localized prompts when the prompt is empty or no profile is selected, so that mistakes are caught before any call
8. As a prompt engineer, I want to pick two successful cells and see their unified diff, so that I inspect output drift precisely
9. As a prompt engineer, I want an experiment history panel (recent runs, preview only), so that I can trace past comparisons
10. As a Chinese-speaking user, I want en/zh copy to follow the st-lang cookie, so that language stays consistent
11. As a platform user, I want dark/light theme to follow the shared theme, so that the page matches the hub
12. As a platform operator, I want the page mounted via the manifest external-app convention, so that ui --build serves it like every workspace
13. As a developer, I want API + Playwright coverage for the migrated page, so that regressions are caught
14. As a developer, I want the Gradio page and its touchpoints removed after cutover, so that only one implementation remains

## Implementation Decisions

- 新建独立 workspace `frontend/prompt_lab`(**目录名必须 = manifest.name "prompt_lab"**,route 仍 /promptlab,vite base '/promptlab/';pitfalls 先例)
- 复用 @shared(card/theme/lang/ReportView);表单+报告形态对标 uitest/llm_eval 先例
- 后端仅加两个薄端点:diff(两段文本+lang → render_diff 的 unified diff markdown,呈现与旧页逐字一致)与 history(ExperimentLogger.recent,preview 不含全文/密钥);run/profiles/health 不动;runner/report/xlog 引擎零改动
- run 保持同步请求 + running 提示;parallel 默认勾选,前端显式传 true(API 默认 false)
- Diff 候选 = run 结果中无 error 的 cells(前端从 run 响应 cells 推导,不需后端新字段);不足两个成功 cell 时按旧页 need_two 文案提示
- manifest 切 external=True, render="";api= 的留空与否按 hub/registry 实际代码核实(react_migration.md 与 orchestrator/llm_eval 先例表述有出入,实施时以避免重复挂载为准)
- i18n 从 Gradio ui _I18N 逐字平移(title/prompt_label/prompt_ph/system_label/system_ph/profiles_label/profiles_hint/report_ph/parallel_label/run_btn/diff_acc/diff_a/diff_b/diff_btn/hist_acc/hist_btn/empty_prompt/no_profiles/need_two/no_history);report.py 的 _I18N 属后端渲染,保留不动
- 退役阶段按 react_migration.md 触点清单(ui.py、hub/css.py 滚动标记、ui_testing/page.py 选择器、cases yaml PLAB1/2、catalog.py、test_registry.py)
- 两批:批次 1 = T1 薄端点 → T2 React MVP+manifest → T3 Diff/历史/i18n → T4 页测+截图+报告;批次 2(用户过目批准)= T5 退役
- UI 约束:禁蓝紫及渐变;manifest color #16a34a(绿)合规不动;三线并行互不阻塞

## Testing Decisions

- 只测外部行为;前端组件不做单测
- 缝 1(REST API):pytest TestClient 覆盖 diff(正常/相同文本 diff_same)、history(空/有记录,PROMPT_LAB_LOG/PROMPT_LAB_PATH env 控制)、run/profiles 回归;先例 tests/test_prompt_lab.py TestApi
- 缝 2(真浏览器):`tests/test_promptlab_page.py`(uitest 标记,in-process uvicorn + dist,先例 test_llmeval_page.py),等价覆盖退役的 PLAB1(空 prompt 提示"请先输入 Prompt")、PLAB2(历史刷新无 Traceback);另:profiles 加载、en/zh 截图(before/after 对比)
- 退役 PLAB1/2 后 uitest 用例下限 34→32
- 验证命令:ruff/mypy/pytest、npm lint/build(prompt_lab workspace)、uitest smoke --no-llm、check_workflow.py
- 真实 LLM 不进自动化;run 路径用 FakeClient/无 key 降级覆盖(TestApi 先例)

## Out of Scope

- runner/report/xlog 引擎改动或新功能;run 的 SSE 流
- 其他页面迁移;main 操作、新分支、PR;前端组件单测

## Further Notes

- 探查依据:manifest(render=ui:render_prompt_lab_page,无 external)、api.py 已有 run/profiles、ui.py 区块与 _I18N、uitest PLAB1/2、tests/test_prompt_lab.py、conftest 默认 PROMPT_LAB_LOG=0
- 用户已在 grilling(Q1–Q6)确认全部决策;api= 留空问题为实施期事实核查项
