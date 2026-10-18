# Spec: Test Data Generator React 迁移

Label: ready-for-agent

## Problem Statement

用户在 hub 的 `/testgen` 页生成测试数据（从查询 SQL/可选 DDL 推导建表与
INSERT，并可在内存 SQLite 上验证），但该页仍是 Gradio 实现，与已迁移的
10 个 React 页不一致。

## Solution

按 docs/react_migration.md 触点清单，以 uitest 骨架 + sql_fmt 先例（含历批
fix-up 教训）迁移为 React，cutover 后退役 Gradio 页及触点。本页为纯确定性
（无 LLM/无连库/无文件），REST 零缺口：`POST /api/testgen/generate`
（report=true）已 1:1 覆盖唯一回调。

**流程约束**：全程在 `ui-build-incremental` 分支串行开发，不建新分支/worktree。

## User Stories

1. 作为数据工程师，我想粘贴查询 SQL（页面预填双表 JOIN 示例）、可选 DDL、选方言（7 种，默认 hive）、拖行数滑杆（1-50，默认 5）、勾选"SQLite 验证"（默认开）点"生成"，得到含建表/INSERT/CSV/验证结果的 Markdown 报告。
2. 作为数据工程师，我想空 SQL 时得到本地化提示；非法 SQL 得到"解析失败"报告而非 Traceback。
3. 作为数据工程师，我想取消 SQLite 验证后报告不含"查询执行成功"段。
4. 作为中文/英文用户，我想 zh/en 全文案切换、暗色模式正确。
5. 作为 API 用户，我想 `POST /api/testgen/generate`、`GET /health` 契约不变（零后端改动）。
6. 作为维护者，我想有 Playwright 页测（TGN1-TGN6 等价）与 i18n parity 测试；cases/testgen.yaml、page.py `.st-tgn-main` 选择器、`_DATA_API_NAMES` 中的 sql_testgen 被干净清理（catalog/css.py 经查无触点）。

## Implementation Decisions

- 新 workspace `sql_testgen`（目录名 = manifest.name），vite base `/testgen/`；
  复用 @shared 全套与 ReportView 先例；Slider/Checkbox 为新控件（原生
  input range/checkbox，样式随 @shared token）。
- 结果区保持 Markdown 报告渲染（grilling Q4：不改用结构化 result）。
- demo SQL 预填在前端复刻（TGN1/TGN2 依赖）。
- 后端零改动：manifest 切 external、hub 无条件挂 router 即可。

## Testing Decisions

- 既有缝：Playwright 页面层（先例 test_sqlfmt_page.py）、REST 契约层
  （test_sql_testgen.py 既有 API 测试保持通过）、i18n 资产层（先例
  test_sqlfmt_i18n.py）。
- 页测覆盖 TGN1-TGN6 等价：预填 JOIN 生成+验证、WHERE 字面量入数据、
  DDL 类型来源、非法 SQL 无 Traceback、取消验证、en 切换；另加空 SQL 提示。
- 不依赖 gitignore 文件（本页无文件依赖）。

## Out of Scope

- generator/report 核心逻辑改动；结构化结果渲染（表格/CSV 原生化）；
  其他页迁移；新功能。

## Further Notes

- 票据 2 张：issues/01-workspace-generate-cutover.md、
  issues/02-page-tests-i18n-cleanup.md。
- before 截图须在退役前截取。
