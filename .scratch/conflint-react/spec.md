# Spec: Config Lint React 迁移

Label: ready-for-agent

## Problem Statement

用户在 hub 的 `/conflint` 页使用 Config Lint（粘贴 HOCON 配置或指定目录做静态
检查），但该页仍是 Gradio 实现，与已迁移的 6 个 React 页（UI Testing Agent、
Config Migrate、Data Comparison、SeaTunnel Pipeline Builder、SQL Review、
Text2SQL）在视觉风格、暗色模式、语言切换体验上不一致，是混合技术栈中遗留的
Gradio 页之一。

## Solution

按既有 React 迁移流程（docs/react_migration.md 13 点触点清单），以 uitest 骨架
为底、config_migrate（最新先例，PR #126）为参照，新建 React workspace 实现
功能 1:1 的 Config Lint 页，cutover 后退役 Gradio 页及其触点。页面行为、路由
（`/conflint`）、REST 契约（`POST /api/conflint/lint`）均保持不变。

**流程约束**：全程在 `ui-build-incremental` 分支串行开发，不建新分支/worktree。

## User Stories

1. 作为数据工程师，我想在 `/conflint` 粘贴 HOCON 配置并点击"Lint 配置"，看到渲染好的 Markdown 检查报告，以便在不执行任务的情况下发现配置问题。
2. 作为数据工程师，我想在输入为空时点击按钮得到明确的空输入提示，以便知道该先粘贴配置。
3. 作为数据工程师，我想展开"目录批量 Lint"面板、输入目录（默认 `examples/conflint_demo`）并点击按钮，得到目录下所有配置的批量报告，以便一次检查整个示例目录。
4. 作为数据工程师，我想在目录不存在或不可读时得到本地化的错误提示，以便修正路径。
5. 作为中文/英文用户，我想用全局语言开关切换 zh/en，页面全部文案（标题、标签、占位符、按钮、警告）随之切换，以便用熟悉的语言工作。
6. 作为暗色模式用户，我想页面配色跟随 hub 的明暗主题，以便与其他 React 页观感一致。
7. 作为 hub 用户，我想 Config Lint 页的卡片、按钮、排版与其他已迁移 React 页同一套设计语言（@shared 主题，无蓝紫色渐变），以便整个产品有一致的视觉。
8. 作为 API 用户，我想 `POST /api/conflint/lint` 与 `GET /api/conflint/health` 契约在迁移后保持不变（含 `CONFLINT_API_ALLOWED_DIRS` 目录白名单），以便已有脚本不受影响。
9. 作为 CLI 用户，我想 `seatunnel-agent conflint` 命令行为不变，以便终端工作流不受迁移影响。
10. 作为编排 Agent 用户，我想 orchestrator 的 `config_lint → /conflint` 路由继续有效，以便编排跳转不断链。
11. 作为维护者，我想该页有 Playwright 页面测试（lint 往返、目录往返、坏目录、语言切换），以便回归可自动发现。
12. 作为维护者，我想 zh/en i18n 键有 parity 测试，以便新增文案不漏翻。
13. 作为维护者，我想 Gradio 版 `ui.py` 与 uitest 用例 `cases/conflint.yaml` 被干净移除、后端 i18n 只保留报告渲染所需键，以便没有死代码。
14. 作为维护者，我想 `seatunnel-agent ui --build` 能增量构建新 workspace，以便本地验证高效。

## Implementation Decisions

- 新建 React workspace `config_lint`（目录名必须等于 manifest.name），vite base `/conflint/`，dev proxy 指向 `/api/conflint`；加入 frontend workspaces 列表。
- 完全复用 `@shared`（theme.css、tailwind-preset、卡片组件、lang.ts cookie 语言桥）；不新增共享组件。
- 前端只调用既有 REST：单配置走 `config` 字段、目录走 `dir` 字段，`report=true` 取 Markdown 报告渲染；后端 linter/report 逻辑零改动。
- i18n 字典从 Gradio 版 UI 字典原样搬入 i18next；后端 i18n 模块裁剪为仅报告渲染所需键。
- cutover：manifest 切 `external=True`、`render=""`；删除 Gradio `ui.py`；REST 挂载方式按触点清单核对，避免双挂载。
- 路由、manifest 元数据（名称、logo、颜色 `#ea580c`、分组）均不变。
- 触点清理：uitest 用例 YAML 及 catalog/page 中 conflint 条目、registry 测试中的硬编码名单、hub css 滚动标记（如有）。
- 批次拆 2 票：①workspace + 全功能 + cutover；②页测 + i18n parity + 触点清理。串行执行，每票独立 commit。

## Testing Decisions

- 只测外部行为：通过真实浏览器（Playwright）驱动页面与通过 REST 契约断言，不测 React 组件内部实现。
- **测试缝（seams，均为既有缝，不新增）**：
  1. Playwright 页面层 —— 对构建产物页面做端到端交互（先例：`tests/test_config_migrate_page.py`）；
  2. FastAPI REST 层 —— `/api/conflint/lint` 契约测试已存在，保持通过；
  3. i18n 资产层 —— zh/en 键 parity 静态校验（先例：`tests/test_config_migrate_i18n.py`）。
- 批次收尾统一跑：ruff / mypy / 全量 pytest / uitest smoke（--no-llm）/ 前后截图对比 / `scripts/check_workflow.py`。

## Out of Scope

- linter 规则、报告格式、REST 契约的任何功能性改动。
- 其他剩余 Gradio 页的迁移。
- 新功能（历史记录、文件上传等 Gradio 版没有的能力）。

## Further Notes

- REST API 先于本次迁移已存在，是改动量最小的一次迁移（页面仅两个动作 + 一个报告区）。
- before 截图需在删除 Gradio 页之前截取（参照 config_migrate 的 shot_old.py 做法）。
- 票据：`issues/01-workspace-lint-cutover.md`、`issues/02-page-tests-i18n-cleanup.md`。
