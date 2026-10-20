# Agent Orchestrator React Migration

Labels: `ready-for-agent`
Branch: `plat`(用户要求:直接在 plat 开发提交,不切新分支、不碰 main)

## Problem Statement

Agent Orchestrator 页面仍是遗留的 Gradio 实现,与已迁移到 React 的其余 17 个 agent 页面(uitest、text2sql、sql_review 等)视觉风格和技术栈不一致:主题/i18n 行为割裂、交互体验(流式步骤展示)受 Gradio 限制、维护两套 UI 栈成本高。

## Solution

按既有 React 迁移先例,把 Orchestrator 页 1:1 对等迁移为独立的 React workspace,复用 @shared 组件与 engineering-paper 主题,聊天形态对齐 text2sql 先例;验证通过后退役 Gradio 旧页。不新增任何功能。

## User Stories

1. As a platform user, I want the Orchestrator page rendered in React with the same visual language as other agent pages, so that the product feels like one coherent system
2. As a platform user, I want to type a request and send it to the orchestrator, so that it routes my task to the right agent
3. As a platform user, I want to see the conversation history in a chat layout, so that I can follow the dialogue
4. As a platform user, I want orchestration steps (tool calls) streamed into the chat as they happen, so that I can see progress on long runs instead of a frozen page
5. As a platform user, I want a "New session" button, so that I can start a fresh conversation
6. As a platform user, I want my session restored when I revisit the page, so that I don't lose context on reload
7. As a platform user, I want the three example buttons (review / chain / pii), so that I can try the orchestrator with one click
8. As a platform user, I want a collapsible "Routable agents" panel, so that I can see which agents the orchestrator can dispatch to
9. As a Chinese-speaking user, I want the page to follow the st-lang cookie (en/zh), so that language stays consistent across all pages
10. As a platform user, I want dark/light theme to follow the shared theme, so that the page matches the rest of the hub
11. As a platform operator, I want the page mounted via the standard manifest external-app convention, so that `seatunnel-agent ui --build` builds and serves it like every other workspace
12. As a developer, I want the Gradio orchestrator page and its touchpoints removed after cutover, so that there is only one implementation to maintain
13. As a developer, I want API and Playwright smoke coverage for the migrated page, so that regressions are caught automatically

## Implementation Decisions

- 新建独立 workspace `frontend/orchestrator`(目录名 = manifest.name),Vite + React + Tailwind + i18next,对标 uitest 工程结构;聊天布局参考 text2sql
- 复用 `@shared`:sse(postSSE)、card 组件、theme.css、lang(st-lang cookie)、bridge/constants
- manifest 切换为 `external=True, render=""`,保留 `route="/orchestrator"` 与已挂的 api router
- 后端仅在 orchestrator api 模块按需新增一个 SSE 流式 run 端点以保留步骤级流式体验;不修改 engine/router/catalog 等编排逻辑;若现有 run 端点已满足流式则不加
- 会话恢复沿用现有会话机制经 API 暴露,前端通过 API 恢复显示,不引入新的持久化方案
- i18n 文案从 Gradio ui 的 en/zh 字典平移到前端 i18next 资源
- 1:1 验收清单:聊天记录、输入框+Send/New session、示例按钮×3、Routable agents 折叠面板、会话恢复、i18n(en/zh)
- 退役阶段按 docs/react_migration.md 触点清单执行:删 Gradio ui 模块及 hub/css、路由映射、catalog、registry 测试硬编码等触点
- 分两批提交:批次 1 = React 页 + manifest 切换 + 必要 SSE 端点 + 验证截图;批次 2 = 退役旧页 + 全量验证;每批独立 commit + 批次报告 + check_workflow.py
- UI 设计约束:禁蓝紫色及渐变,风格与现有 React 页一致

## Testing Decisions

- 只测外部行为,不测组件内部实现;前端组件不做单测(仓库无此先例)
- 缝 1(REST/SSE API):pytest + FastAPI TestClient 覆盖 run(含流式事件序列)、agents 列表端点;先例为 uitest api 测试与 tests/test_orchestrator.py
- 缝 2(真浏览器):uitest smoke 套件新增 orchestrator 页用例(Playwright),覆盖页面加载、发送消息、示例按钮、agents 面板;先例为 dag_check/text2sql 迁移的 Playwright 覆盖
- 验证命令:ruff check src tests、mypy、pytest、npm lint/build(orchestrator workspace)、`python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm`、check_workflow.py
- UI 验收:uitest 产出迁移前后截图对比,入批次报告,用户过目后批次才算完成

## Out of Scope

- 任何新功能、编排逻辑(engine/router/catalog/prompts)改动
- 其他页面的迁移或重构;顺手重构
- main 分支操作、新分支、PR 流程
- 前端组件级单元测试

## Further Notes

- 当前分支 plat 工作区干净;直接在 plat 上分批提交
- Gradio 版步骤流式用 worker thread + queue;React 版以 SSE 对等承接,事件粒度保持"每个工具调用一条步骤消息"
- 用户已在 grilling 会话中确认全部设计决策(Q1–Q9 均 yes)
