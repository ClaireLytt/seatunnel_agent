# Spec: DAG Health Check 页 React 迁移

Labels: `ready-for-agent`

## Problem Statement

作为维护者,data 工作区 18 页中仅剩 3 个 Gradio 页(dagcheck/loginspect/mcp)。/dagcheck 与已迁 React 页风格割裂,且仍依赖 uitest yaml(DAG1-5)而非统一的 Playwright 覆盖,维护两套 UI 栈成本高。

## Solution

按 `docs/react_migration.md` 清单把 DAG Health Check 完整切换为 React workspace(形态对标 form→report 类先例如 metric_diff/pii_scan):同一路由 `/dagcheck`、功能 1:1、双语对齐、Gradio 页退役、DAG1-5 yaml 退役并由 Playwright 页面测试对等(含 uitest-coverage 批确立的按钮级覆盖标准)。

## User Stories

1. As a 数据工程师, I want 在 /dagcheck 看到与其他 React 页一致的界面, so that 平台体验统一。
2. As a 数据工程师, I want 填 SQL 目录(默认 examples/dagcheck_demo)点"体检 DAG"得到报告, so that 原有工作流不变。
3. As a 数据工程师, I want 可选填 SeaTunnel 配置目录, so that 体检涵盖同步任务依赖。
4. As a 数据工程师, I want 方言下拉保留 7 项(hive 默认), so that 各方言 SQL 均可体检。
5. As a 数据工程师, I want 坏目录时得到"不是有效目录"类提示而非 traceback, so that 错误可理解。
6. As a 中文/英文用户, I want 页面随 st-lang cookie 双语切换且文案与 Python i18n 对齐, so that 双语体验一致。
7. As a 维护者, I want manifest 转 external、`api=` 清空、router 改 hub 挂载, so that 不发生双挂载(react_migration.md 已知坑)。
8. As a 维护者, I want Gradio ui.py 删除、页面触点(page.py/catalog/css/yaml/测试硬编码)按手册清理, so that 无死代码残留。
9. As a 维护者, I want tests/test_dagcheck_page.py 对等覆盖 DAG1-5(环/分批+关键路径/不可调度/坏目录/英文流), so that 回归保护不降级。
10. As a 维护者, I want 新页每个控件至少被测试点一次 + 非默认方言用例, so that 符合 uitest-coverage 批的覆盖标准。
11. As a 维护者, I want i18n parity 测试(先例 test_seatunnel_i18n.py 模式), so that 双语 key 不漂移。
12. As a 维护者, I want 迁移前后截图落盘报告, so that UI 改动可视化验收。

## Implementation Decisions

- 完整切换,不保留 Gradio 并行;路由不变 `/dagcheck`;workspace 目录名必须等于 manifest.name:`frontend/dag_check/`。
- 从 uitest 骨架复制 workspace;vite `base:'/dagcheck/'`、dev proxy `/api/dagcheck`;加入根 package.json workspaces;复用 @shared(theme.css/tailwind-preset/卡片组件/lang.ts);无长任务,不用 sse.ts。
- 复用现有 `POST /api/dagcheck/check`(请求 {sql_dir, seatunnel_dir?, dialect, lang, report});manifest `api=` 置空、`external=True`、`render=""`,router 在 hub/ui.py 无条件挂载;目录白名单行为不变。
- 报告区渲染 API 返回的 markdown `report` 字段;form→report 形态,不做 dashboard 化(保持简单)。
- i18n:i18next 资源从 dag_check/i18n.py 原样复制;UI-chrome keys 从 Python 侧裁剪,报告模板 keys 保留(报告由后端生成)。
- UI 规范:禁蓝紫色;图形/按钮优先于解释文字;视觉与既有 React 页一致。
- 退役触点(react_migration.md 清单):ui.py 删除;hub/css.py 页面段;ui_testing/page.py(READY routes/LABELS/结果选择器×3);cases/dagcheck.yaml 删除;catalog.py AGENT_ROUTES/AGENT_LABELS;test_registry.py `_DATA_API_NAMES`、test_ui_testing.py 覆盖断言(yaml 用例 floor 43→38)。
- 开发在 `ui-build-incremental` 分支进行(用户指定,不切新分支);#125 已合并,分支已同步 origin/main。

## Testing Decisions

- 好测试 = 外部行为:点击后报告区内容、提示文案、语言切换结果;不断言组件内部。
- tests/test_dagcheck_page.py(Playwright,in-process uvicorn,先例 tests/test_metricdiff_page.py / test_pii_page.py):smoke(标题/默认值/按钮)、demo 目录出环+断链(对等 DAG1)、分批+关键路径(DAG2)、不可调度表(DAG3)、坏目录无 traceback(DAG4)、英文流(DAG5)、非默认方言(spark)、空输入提示;共用 conftest 的 assert_dialect_switch。
- i18n parity 测试照既有模式;API 已有 tests 不动。
- 验证:ruff/mypy/定向 pytest;收尾全量 pytest + uitest smoke + 截图 + check_workflow。

## Out of Scope

- loginspect、mcp 两页的迁移。
- dagcheck 新功能(下载报告、历史记录等)。
- checker.py/report.py 后端逻辑改动。

## Further Notes

- 盘点:ui.py 仅 5 控件,无 LLM 依赖,全确定性——最简迁移类。
- 旧页截图需在删除 ui.py 前抓取(或 git worktree 回看,Gradio 截图需 wait_until="load")。
