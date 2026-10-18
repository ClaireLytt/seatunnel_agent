# Spec: SQL Formatter React 迁移

Label: ready-for-agent

## Problem Statement

用户在 hub 的 `/sqlfmt` 页使用 SQL Formatter（粘贴 SQL 选方言格式化，或检查
目录下 *.sql 的格式化需求），但该页仍是 Gradio 实现，与已迁移的 7 个 React 页
（含刚完成的 Config Lint）视觉与工程结构不一致。

## Solution

按 docs/react_migration.md 触点清单，以 uitest 骨架 + 最新先例
`frontend/config_lint`（commit 1623dd9/a437522）为参照，新建 React workspace
实现功能 1:1 的 SQL Formatter 页，cutover 后退役 Gradio 页及触点。

**REST 缺口**：目录检查（`do_check_dir` → `fmt_dir(write=False)` +
`render_batch_markdown`）无 REST 端点。按 conflint API 形状补：现有
`POST /api/sqlfmt/format` 增加可选 `dir` 字段（`sql`/`dir` 二选一），目录走
`require_dir` + 新白名单环境变量 `SQLFMT_API_ALLOWED_DIRS`，`write=False`
只检查不写；向后兼容，formatter 核心零改动。

**流程约束**：全程在 `ui-build-incremental` 分支串行开发，不建新分支/worktree。

## User Stories

1. 作为数据工程师，我想粘贴 SQL、选择方言（hive/spark/mysql/postgresql/clickhouse/doris/starrocks，默认 hive）点"格式化"，看到 Markdown 格式化报告。
2. 作为数据工程师，我想在输入为空时得到本地化空输入提示。
3. 作为数据工程师，我想展开"检查目录"输入目录（默认 `examples/sqlfmt_demo`）得到批量检查报告（只检查不写文件）。
4. 作为数据工程师，我想目录非法时得到本地化 bad_dir 提示（结构化 detail，白名单前置，同 conflint fix-up 后形状）。
5. 作为中文/英文用户，我想 zh/en 全文案随全局语言开关切换。
6. 作为暗色模式用户，我想页面配色跟随 hub 明暗主题，与其他 React 页一致。
7. 作为 API 用户，我想现有 `POST /api/sqlfmt/format`（内联 sql）与 `GET /health` 契约不变，新增 `dir` 字段向后兼容。
8. 作为维护者，我想有 Playwright 页测（覆盖退役的 FMT1-FMT6 YAML 用例等价场景）与 zh/en i18n parity 测试。
9. 作为维护者，我想 Gradio ui.py、cases/sqlfmt.yaml、page.py 的 `.st-fmt-main` 选择器、`_DATA_API_NAMES` 中的 sql_fmt 被干净清理。

## Implementation Decisions

- 新 workspace `sql_fmt`（目录名 = manifest.name），vite base `/sqlfmt/`，复用 @shared 全套；方言下拉为新增 UI 控件（React select，样式随 @shared）。
- API：单端点扩展（可选 `dir`），目录分支 = 白名单检查（`check_path_allowed` 前置）→ 结构化 bad_dir → `fmt_dir(write=False)` → `render_batch_markdown`；响应复用现有形状（batch 时 result 为批量 dict 列表）。
- manifest 切 external、`render=""`、api= 置空改 hub 无条件挂载；路由/颜色/分组不变。
- i18n 字典原样搬 i18next；后端 report 键留 Python。
- 2 票：①workspace+全功能+API dir 扩展+cutover；②页测+parity+触点清理+批次收尾。

## Testing Decisions

- 既有缝：Playwright 页面层（先例 tests/test_conflint_page.py）、REST 契约层（tests/test_sql_fmt.py 既有 API 测试保持通过 + 新 dir 分支测试）、i18n 资产层（先例 tests/test_conflint_i18n.py）。
- 页测覆盖 FMT1-FMT6 等价：格式化往返、无需改动、风格提示、解析失败无 Traceback、目录检查、en 语言切换；另加空输入与 bad_dir。
- 批次收尾统一跑 ruff/mypy/全量 pytest/uitest smoke/截图/check_workflow + 双轴 code-review。

## Out of Scope

- formatter/report 核心逻辑改动；其他 Gradio 页迁移；新功能（写回文件、下载等）。

## Further Notes

- aiplatform.yaml:130 断言页面出现 `sql_fmt` 文本——清理时核对该用例是否受影响。
- before 截图须在退役前截取（.scratch/sqlfmt-react/shot_old.py）。
