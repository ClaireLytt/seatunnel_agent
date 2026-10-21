# Doc Q&A React Migration

Labels: `ready-for-agent`
Branch: `plat`(用户要求:直接在 plat 开发提交,不切新分支)

## Problem Statement

Doc Q&A 页面(/docqa)仍是遗留 Gradio 实现,与已迁 React 的页面(含本轮 AI Platform 四页)视觉与技术栈不一致,维护两套 UI 栈成本高。

## Solution

按既有迁移先例把 Doc Q&A 1:1 迁为独立 React workspace:问题输入、"用 LLM 作答"开关、Ask 按钮、Markdown 答案报告(含命中来源/摘录)。复用 @shared 与 engineering-paper 主题;验证通过后退役 Gradio 旧页。不加新功能、零后端改动。

## User Stories

1. As a platform user, I want the Doc Q&A page rendered in React with the shared visual language, so that the product feels coherent
2. As a docs reader, I want a question input (multi-line) with a placeholder example, so that I know what to ask
3. As a docs reader, I want an "answer with LLM" toggle (off by default), so that I choose extractive vs LLM answers
4. As a docs reader, I want an Ask action (button and Enter submit), so that I get an answer quickly
5. As a docs reader, I want the answer rendered as a Markdown report with sources and excerpts, so that I can verify where it came from
6. As a docs reader, I want a localized notice when I ask with an empty question, so that mistakes are caught before any request
7. As a docs reader, I want errors shown inline (⚠️ detail), so that failures are visible without a broken page
8. As a Chinese-speaking user, I want en/zh copy to follow the st-lang cookie, so that language stays consistent
9. As a platform user, I want dark/light theme to follow the shared theme, so that the page matches the hub
10. As a platform operator, I want the page mounted via the manifest external-app convention, so that ui --build serves it like every workspace
11. As a developer, I want Playwright coverage for the migrated page, so that regressions are caught
12. As a developer, I want the Gradio page and its touchpoints removed after cutover, so that only one implementation remains

## Implementation Decisions

- 新建独立 workspace `frontend/doc_qa`(**目录名 = manifest.name "doc_qa"**,route 仍 /docqa,vite base '/docqa/';datacompare 命名坑照规避)
- 复用 @shared(card/theme/lang/ReportView);表单+报告形态对标 prompt_lab/llm_cost 最新先例
- **零新端点、引擎零改动**:现有 ask 端点已覆盖(question/llm/lang;k 固定 4 不暴露,维持旧页行为);空问题前端拦截显示 empty 文案(API min_length 校验仅兜底);语言切换纯前端
- running 状态提示(LLM 模式可能数秒),错误 ⚠️ detail 显示
- manifest 切 external=True, render="";api= 保留(hub 无条件挂载,先例已核实)
- i18n:UI 字典(title/q_label/q_ph/llm_label/ask_btn/report_ph/empty)平移 i18next;answer 模块的后端渲染键(no_hit/sources/excerpt/llm_failed 等)保留 Python 侧
- 精简三票链(页面小,不套五票):T1 React 页完整 + manifest 切换 → T2 页测+截图+批次 1 报告 → T3 退役(用户过目批准后)
- UI 约束:禁蓝紫及渐变;manifest color #0891b2(青)合规不动

## Testing Decisions

- 只测外部行为;前端组件不做单测
- 缝(真浏览器):`tests/test_docqa_page.py`(uitest 标记,in-process uvicorn + dist,先例 test_llmcost_page.py):en 冒烟(控件/无 console error)、提问走 extractive 路径返回含来源的报告(确定性,不调 LLM)、空问题本地提示且不发请求、en/zh 截图(before/after 对比)
- 无 uitest yaml 用例可退役,用例数下限保持 29;API 既有测试(tests/test_doc_qa.py)回归即可,无需新增 API 测试
- 验证命令:ruff/mypy/pytest、npm lint/build(doc_qa workspace)、uitest smoke --no-llm、check_workflow.py
- 不调真实 LLM;extractive 路径确定性覆盖

## Out of Scope

- 引擎(core/answer)改动、新端点、暴露 k 参数、聊天/会话形态、流式
- 其他页面迁移;main 操作、新分支、PR;前端组件单测

## Further Notes

- 探查依据:manifest(render=ui:render_doc_qa_page,无 external)、api.py 的 ask/health、ui.py 区块与 _I18N、索引为进程内缓存无磁盘持久化、tests/test_doc_qa.py、uitest 无 docqa 用例
- 用户已在 grilling(Q1–Q5)确认全部决策,含三票精简链
