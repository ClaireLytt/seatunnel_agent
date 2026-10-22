# Spec: CI Log Triage(ci_inspect)页面 React 迁移

Label: `ready-for-agent`

## Problem Statement

CI Log Triage(`/ciinspect`)仍是遗留 Gradio 页(剩余 7 个未迁移页之一),与已迁移到 React 的其他 agent 页面风格/架构不一致:无 @shared 统一组件与主题、无独立 workspace 构建、仍依赖 Gradio uitest 引擎(devops.yaml CI1 用例)维护成本高。

## Solution

按已完成的 React 迁移先例(以 issue_triage 为模板——同为"粘贴文本→运行→Markdown 报告"形态)新建 ci_inspect React workspace,完成 manifest cutover(external 挂载),退役 Gradio 页及其 uitest 触点,改用页级 Playwright 测试。开发直接在 `feat/ui-build-parallel` 分支进行(用户明确要求同分支、不切新分支)。

## User Stories

1. As a 开发者, I want 在 `/ciinspect` 打开与其他已迁移页一致的 React 界面, so that 全站视觉与交互统一
2. As a 开发者, I want 粘贴 CI 日志文本并点击运行得到 triage 分析报告(Markdown 渲染), so that 与原 Gradio 页功能等价
3. As a 中文用户, I want 界面语言跟随现有 i18n 机制切换 en/zh, so that 原 Gradio 页的双语能力不丢失
4. As a 开发者, I want 页面经由 manifest external 挂载(与 issue_triage 同机制), so that hub 路由/导航无需特殊处理
5. As a 开发者, I want 新 workspace 纳入 `ui --build` 增量+并行构建, so that 构建流程零额外配置
6. As a 仓库维护者, I want Gradio ui.py 及 hub/uitest 中该页的全部触点按退役清单清理, so that 不留死代码
7. As a 仓库维护者, I want devops.yaml 的 CI1 用例替换为页级 Playwright 测试, so that 真浏览器验证不依赖 Gradio uitest 引擎
8. As a 仓库维护者, I want 新 workspace 的 lint 被 CI 全 workspace lint 覆盖, so that 质量门禁自动生效
9. As a 开发者, I want 后端分析能力经现有 REST 路由暴露给前端(与先例同模式), so that 前后端解耦
10. As a 开发者, I want 错误与加载状态有明确 UI 反馈(复用 @shared 既有组件), so that 分析失败时可感知
11. As a 仓库维护者, I want 迁移不改变 agent 的分析逻辑本身, so that 行为回归风险最小

## Implementation Decisions

- 模板先例:issue_triage workspace(最近迁移波中最小、形态相同);按 docs/react_migration.md 触点清单执行(新 workspace 步骤、cutover 步骤、退役 blast-radius 清单)。
- workspace 目录名必须等于 manifest.name(`ci_inspect`),vite base 为路由路径;复用 @seatunnel/shared 组件/主题/router factory;i18n 从 Gradio ui.py 的 en/zh 词典平移。
- cutover:manifest 改 `external=True`、`render=""`;删除 Gradio ui.py;清理 hub css 标记、ui_testing page/catalog 的路由与标签、devops.yaml CI1 用例、test_registry/test_ui_testing 硬编码。
- 后端 API:沿用该 agent 现有 REST 暴露方式;若尚无 REST 端点,按先例最小新增(文本入、报告出),不扩展分析逻辑。
- UI 遵守项目规范:禁蓝紫色渐变,与已迁移页视觉一致,不加多余解释文字。
- 分支:直接在 `feat/ui-build-parallel` 上开发(用户指令覆盖 CLAUDE.md 从 main 切分支的默认规范;已向用户提示混合改动的 review/回滚代价,用户确认)。
- 顺序:待 ui-build-parallel 批次收尾完成后动码;优先于 Secret Scan 迁移(后者另行等批准)。

## Testing Decisions

- 只测外部行为:真浏览器打开 `/ciinspect`,断言标题/输入框/运行按钮存在、提交样例日志后报告区出现内容;不断言组件内部实现。
- 页级 Playwright 测试,先例为已迁移页的 `tests/test_<name>_page.py` 模式(如 issue_triage 的页测);归 uitest marker,默认 pytest 跳过。
- 退役触点的回归:现有 test_registry / test_ui_testing 相关断言更新后须全绿。
- 验证命令:ruff / mypy / 定向 pytest + `npm run lint --workspace` + `npm run build --workspace`;批次收尾跑 uitest smoke 与 `seatunnel-agent ui --build`。

## Out of Scope

- ci_inspect 分析逻辑/提示词的任何增强或修改。
- 其余 6 个未迁移 Gradio 页(log_inspect、mcp_toolbox、dep_check、doctor、release_notes、secret_scan——secret_scan 已另有规划待批)。
- Gradio uitest 引擎本身的退役。
- 新功能(历史记录、文件上传等 Gradio 页没有的能力)。

## Further Notes

- 剩余 Gradio 页共 7 个;本 spec 完成后剩 6 个。
- 与 ui-build-parallel 批次同分支交付,PR 将包含两类改动,review 时注意按 commit 分界。
