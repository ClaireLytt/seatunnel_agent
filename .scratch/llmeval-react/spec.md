# LLM Eval React Migration

Labels: `ready-for-agent`
Branch: `plat`(用户要求:直接在 plat 开发提交,不切新分支)

## Problem Statement

LLM Eval 页面(/llmeval)仍是遗留 Gradio 实现,与已迁 React 的 18 个页面(含刚迁的 orchestrator)视觉与技术栈不一致:主题/i18n 割裂、matplotlib 趋势图与前端图表体系(Recharts)不统一、维护两套 UI 栈成本高。

## Solution

按既有迁移先例把 LLM Eval 页 1:1 迁为独立 React workspace:套件 YAML 编辑器、载入示例、仅解析校验、LLM judge 开关、运行评测、Markdown 报告区、历史趋势图(Recharts)。复用 @shared 与 engineering-paper 主题;验证通过后退役 Gradio 旧页。不加新功能。

## User Stories

1. As a platform user, I want the LLM Eval page rendered in React with the shared visual language, so that the product feels coherent
2. As an eval author, I want a YAML suite editor with a placeholder example, so that I know the expected format
3. As an eval author, I want a "load demo suite" button, so that I can try the feature with one click
4. As an eval author, I want a "validate suite" action that only parses (no LLM call), so that I catch format errors cheaply
5. As an eval author, I want clear localized errors when the suite YAML is invalid or empty, so that I can fix it quickly
6. As an eval runner, I want a "run suite" button with an LLM-judge toggle, so that I control scoring cost
7. As an eval runner, I want a running indicator while the suite executes, so that I know the request is in flight
8. As an eval runner, I want the result rendered as a Markdown report with regression comparison against the previous run, so that I see pass/fail and drift at a glance
9. As an eval runner, I want a history trend chart of past runs, so that I can watch quality over time
10. As a Chinese-speaking user, I want en/zh copy to follow the st-lang cookie, so that language stays consistent
11. As a platform user, I want dark/light theme to follow the shared theme, so that the page matches the hub
12. As a platform operator, I want the page mounted via the standard manifest external-app convention, so that `ui --build` serves it like every workspace
13. As a developer, I want API + Playwright coverage for the migrated page, so that regressions are caught
14. As a developer, I want the Gradio page and its touchpoints removed after cutover, so that only one implementation remains

## Implementation Decisions

- 新建独立 workspace `frontend/llm_eval`(目录名 = manifest.name),工程结构对标 uitest/orchestrator;表单+报告形态参考 uitest 页(非聊天形态)
- 复用 `@shared`(card、theme.css、lang、api/constants);趋势图用 Recharts(先例 uitest CountsChart),数据来自既有 history 端点,后端不再出图
- 后端仅加两个薄端点:validate(调 parse_suite,返回 ok 或本地化错误)与 demo(返回示例套件文本);run/history/health 不动;suite/runner/scoring/baseline/report 引擎零改动
- run 保持同步一次性请求(无 SSE),前端 running 状态提示,judge 开关映射 run 的 judge 参数
- manifest 切 external=True, render="",route /llmeval 与 api router 不变
- i18n 文案从 Gradio ui 的 _I18N(title/suite_label/suite_ph/demo_btn/validate_btn/valid_ok/report_ph/judge_label/run_btn/trend_acc/trend_btn/empty_suite/no_runs/running)平移到 i18next
- 1:1 验收清单:套件编辑器、载入示例、校验(含空套件提示)、judge 开关、运行+报告、趋势图、i18n
- 退役阶段按 docs/react_migration.md 触点清单删 Gradio ui 模块及触点(含 matplotlib 趋势图代码)
- 两批提交:批次 1 = React 页 + validate/demo 端点 + manifest 切换 + 页测截图;批次 2(用户过目批准后)= 退役旧页;每批 commit + 报告 + check_workflow.py
- UI 约束:禁蓝紫及渐变;与 Orchestrator 迁移并行推进、互不阻塞(文件不相交)

## Testing Decisions

- 只测外部行为;前端组件不做单测(仓库无先例)
- 缝 1(REST API):pytest TestClient 覆盖 validate(合法/非法/空)、demo、run 既有行为回归;先例 tests/test_llm_eval.py TestApi
- 缝 2(真浏览器):`tests/test_llmeval_page.py`(uitest 标记,in-process uvicorn + dist,先例 test_orchestrator_page.py / test_dagcheck_page.py),等价覆盖退役的 yaml 用例 EVAL1(载入示例含 text2sql-golden)、EVAL2(非法套件报"期望顶层"且无 Traceback)、EVAL3(空套件提示"请先粘贴");另覆盖 en/zh 截图(before/after 对比入 docs/reports/shots/)
- 退役 yaml 用例后同步调低 uitest 用例数下限(先例:ORCH1 退役 38→37)
- 验证命令:ruff/mypy/pytest、npm lint/build(llm_eval workspace)、uitest smoke --no-llm、check_workflow.py
- 真实 LLM 运行不进自动化(与仓库惯例一致);运行路径用无 key 降级/确定性 checker 覆盖

## Out of Scope

- 任何评测引擎(suite/runner/scoring/baseline/report)功能改动或新功能
- run 的 SSE 进度流(记遗留,另批)
- 其他页面迁移;main 分支操作、新分支、PR
- 前端组件级单元测试

## Further Notes

- 探查依据:manifest(render=ui:render_llm_eval_page,无 external)、api.py 已有 run/history/health、ui.py 区块与 _I18N 键、uitest 用例 EVAL1–3、tests/test_llm_eval.py;docs 无该页特殊 pitfalls
- manifest color #0ea5e9(青蓝)不属蓝紫禁区,保持不动
- 用户已在 grilling(Q1–Q7)确认全部决策
