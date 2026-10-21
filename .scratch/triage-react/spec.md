# Issue Triage React Migration

Labels: `ready-for-agent`
Branch: `plat`(用户要求:直接在 plat 开发提交,不切新分支)

## Problem Statement

Issue Triage 页面(/triage)仍是遗留 Gradio 实现,与已迁 React 的页面不一致,维护两套 UI 栈成本高;且 REST run 端点与旧页行为有一处偏差(旧页用服务端 demo 历史库查重,REST 只接受内联历史,前端无法对齐)。

## Solution

把 Issue Triage 1:1 迁为独立 React workspace:issue 标题/正文输入、Triage 按钮、Markdown 分诊报告(labels/duplicates/priority/draft 回复)。run 端点在未提供 issues 时默认加载 demo 历史库(对齐旧页),显式空列表表示无历史。验证通过后退役 Gradio 旧页。

## User Stories

1. As a platform user, I want the Issue Triage page rendered in React with the shared visual language, so that the product feels coherent
2. As a maintainer, I want title and body inputs for a new issue, so that the agent can triage it
3. As a maintainer, I want a Triage action with a running indicator, so that I know the request is in flight
4. As a maintainer, I want the result as a Markdown report (suggested labels, likely duplicates, priority, draft reply), so that I can act on it quickly
5. As a maintainer, I want duplicate search to run against the bundled demo history by default, so that the page behaves like it always has
6. As a maintainer, I want an empty title caught locally with a localized notice, so that no request is wasted
7. As a maintainer, I want a clear notice when no LLM key is configured (503), so that I know to configure settings
8. As a Chinese-speaking user, I want en/zh copy to follow the st-lang cookie, so that language stays consistent
9. As a platform user, I want dark/light theme to follow the shared theme, so that the page matches the hub
10. As a platform operator, I want the page mounted via the manifest external-app convention, so that ui --build serves it like every workspace
11. As a developer, I want API + Playwright coverage for the migrated page, so that regressions are caught
12. As a developer, I want the Gradio page and its touchpoints removed after cutover, so that only one implementation remains

## Implementation Decisions

- 新建独立 workspace `frontend/issue_triage`(目录名 = manifest.name,route 仍 /triage,vite base '/triage/')
- 复用 @shared(card/theme/lang/ReportView);表单+报告形态对标 doc_qa 最新先例
- 后端唯一小改:run 请求的 issues 字段改为可空——未提供(None)时服务端加载 demo 历史 JSONL(与旧页一致),显式 [] 表示无历史;其余(repo_dir=None 不做代码 grep、同步一次性返回、无 SSE)保持现状;engine/report 零改动
- 前端:title/body 输入 + Triage 按钮 + running 提示;空 title 本地拦截(empty 文案);503(无 key)/502 错误 ⚠️ detail 显示(no_key 语义由 detail 文案承载)
- manifest 切 external=True, render="";api= 保留
- i18n:UI 字典(title/t_label/b_label/run_btn/report_ph/empty/no_key)平移 i18next;report 模块后端渲染键保留 Python 侧
- 三票链:T1 React 页完整 + /run demo 默认值(含测试)+ manifest 切换 → T2 页测+截图+批次 1 报告 → T3 退役(用户过目批准后);T1+T2=批次 1
- UI 约束:禁蓝紫及渐变;manifest color #9333ea(紫)为既有违规项,本次不动,入遗留清单与 orchestrator #7c3aed 一并由用户定夺

## Testing Decisions

- 只测外部行为;前端组件不做单测
- 缝 1(REST API):TestClient 覆盖——issues 省略时 demo 历史生效(查重命中 demo 库中的已知 issue)、显式 [] 无历史、无 key 503、fake LLM 200+report 回归;先例 tests/test_issue_triage.py TestCliAndApi + ScriptedClient
- 缝 2(真浏览器):`tests/test_triage_page.py`(uitest 标记,先例 test_docqa_page.py):en 冒烟、空 title 本地提示且不发请求、无 key 时 503 detail 内联显示(确定性,不调真实 LLM)、en/zh 截图(before/after)
- 无 uitest yaml 用例退役,下限保持 29
- 验证命令:ruff/mypy/pytest、npm lint/build(issue_triage workspace)、uitest smoke --no-llm、check_workflow.py

## Out of Scope

- engine/report 改动、SSE、repo_dir 开放、自定义历史库上传 UI
- 其他页面迁移;main 操作、新分支、PR;前端组件单测

## Further Notes

- 探查依据:manifest(render=ui:render_issue_triage_page,无 external)、api.py run/health(issues 内联、repo_dir=None)、ui.py 区块与 _I18N、demo 数据 examples/triage_demo/issues.jsonl、tests/test_issue_triage.py、uitest 无用例
- 用户已在 grilling(Q1–Q5)确认全部决策
