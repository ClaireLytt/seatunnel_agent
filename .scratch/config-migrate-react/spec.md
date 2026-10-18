# Spec: DataX/Sqoop Migration(config_migrate)页 React 迁移

Label: ready-for-agent

## Problem Statement

DataX/Sqoop Migration 页仍是 Gradio 实现,与已迁移的 5 个 React 页(uitest、data_comparison、seatunnel、sql_review、text2sql)视觉与技术栈不一致;Gradio 页交互细节受限,且 hub 的 React 化进程要求逐页退役 Gradio。

## Solution

按既有迁移先例(最接近 data_comparison 的表单→输出模式)把 config_migrate 迁为 React workspace:1:1 功能对等(单条迁移、批量目录迁移、中英切换、yaml 输出、Markdown 报告),REST API 挂 hub,manifest 标 external,同批次退役 Gradio 页并清理全部触点(docs/react_migration.md 13 条)。

## User Stories

1. As a 数据工程师, I want 在 React 页粘贴 DataX job JSON 或 sqoop 命令并点击 Migrate, so that 得到等价的 SeaTunnel 配置。
2. As a 数据工程师, I want 迁移结果以 yaml 代码块展示并可复制、带语法高亮, so that 与原 gr.Code 体验对等。
3. As a 数据工程师, I want 看到 Markdown 迁移报告(映射说明/不兼容项), so that 了解迁移质量。
4. As a 数据工程师, I want 填服务器任务目录与输出目录做批量迁移, so that 一次迁移整目录任务(与现版行为一致,仍为服务器路径模式)。
5. As a 批量用户, I want 批量结果报告(成功/失败清单), so that 知道哪些任务需人工处理。
6. As a 中文用户, I want 页面中英切换与其他 React 页一致(st-lang cookie + i18next), so that 语言体验统一。
7. As a hub 用户, I want /migrate 路由由 React 静态页接管、未构建时显示提示页, so that 与其他 external 页行为一致。
8. As a 维护者, I want 旧 Gradio ui.py 删除且所有触点(css、uitest 路由/用例/catalog、registry 测试)清理干净, so that 不留双轨残骸。
9. As a 测试维护者, I want 等价的 Playwright 页面测试与 i18n parity 测试, so that 覆盖不因退役 YAML 用例而下降。
10. As a 用户, I want 迁移失败时有明确错误提示, so that 知道输入哪里不被支持。

## Implementation Decisions

- 新建 React workspace,目录名必须等于 manifest name(config_migrate),复制 uitest 骨架:vite base 为页面路由、dev proxy /api/config_migrate→7860;frontend 根 package.json workspaces 登记。
- 复用 @shared:theme.css、tailwind-preset、card 组件、langFromCookie;无长任务,不用 sse.ts。
- REST API:新建 agents/data/config_migrate/api.py,APIRouter prefix=/api/config_migrate,端点:单条迁移(文本入,返回 yaml + 报告 markdown + 不兼容清单)、批量迁移(任务目录+输出目录入,返回批量报告);复用 migrator.migrate_text/migrate_dir 与 report 渲染,lang 参数保留(后端渲染 key)。
- router 在 hub launch 后无条件挂载(与 datacompare 同模式),manifest 的 api 字段留空。
- i18n:_I18N 字典逐字平移到 i18next 资源;Python 侧仅删 UI-chrome key,后端渲染 key(report.py 用)保留。
- manifest 改 external=True、render="";静态挂载走 registry.frontend_dist 约定。
- yaml 输出用轻量语法高亮;先查 sql_review/text2sql 是否已有代码高亮先例组件,有则复用,无则选最小库。
- 退役触点:删 ui.py;hub/css.py 该页段;ui_testing/page.py 三处(READY 路由映射/LABELS/结果区选择器);cases/*.yaml 中该页用例改写为 tests/test_config_migrate_page.py(Playwright in-process);ui_testing/catalog.py AGENT_ROUTES/AGENT_LABELS;tests/test_registry.py 与 test_ui_testing.py 相关断言。
- 批量模式保留服务器路径语义(1:1),浏览器上传/下载模式记为遗留增强。

## Testing Decisions

- API 层:pytest 直测新 router(FastAPI TestClient),覆盖单条成功/不支持输入/批量成功与部分失败;不 mock migrator(纯规则、快)。
- 页面层:Playwright in-process uvicorn 测试(照 tests/test_<name>_page.py 先例):页面加载、单条迁移出 yaml 与报告、批量表单提交、语言切换。
- i18n parity:照 tests/test_datacompare_i18n.py 先例,断言 i18next 资源与保留的后端 key 一致性。
- 旧 YAML 用例等价覆盖后删除;uitest smoke 全量跑于批次收尾。
- 截图前后对比:旧页用 git worktree 起迁移前 commit(Gradio 页 Playwright wait_until="load")。

## Out of Scope

- 批量迁移的浏览器上传/打包下载模式。
- migrator 规则本身的增强或修复。
- 其他 Gradio 页的迁移。

## Further Notes

- 先例速查:表单→输出页照 data_comparison;workspace 目录名=manifest name 是已踩过的坑(docs/react_migration.md)。
- 改前端后用 `seatunnel-agent ui --build`(本次已增量化,仅重建本 workspace)。
