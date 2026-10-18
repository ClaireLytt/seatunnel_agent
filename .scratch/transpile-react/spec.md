# Spec: SQL Dialect Translation React 迁移

Label: ready-for-agent

## Problem Statement

用户在 hub 的 `/transpile` 页做 SQL 方言翻译（单条/批量、可选 LLM 建议），
但该页仍是 Gradio 实现，与已迁移的 8 个 React 页视觉与工程结构不一致。

## Solution

按 docs/react_migration.md 触点清单，以 uitest 骨架 + 最新先例
`frontend/sql_fmt`/`config_lint`（含 code-review fix-up 后形状）为参照，新建
React workspace 实现功能 1:1 的翻译页，cutover 后退役 Gradio 页及触点。

**REST 缺口补齐**（核心零改动）：
1. `POST /api/transpile/advice`：入参原 SQL + 方言对 + lang，服务端重跑
   transpile 得 result 再 `generate_advice`；无 key / 无可建议项返回结构化
   状态（`{code: "no_key"}` / `{code: "none"}`）由前端本地化。
2. `/batch` 加可选 `out_dir`（写盘），输入与输出目录都走
   `TRANSPILE_API_ALLOWED_DIRS` 白名单（读写双向受限）。

**流程约束**：全程在 `ui-build-incremental` 分支串行开发，不建新分支/worktree。

## User Stories

1. 作为数据工程师，我想选源方言（含 Auto detect，默认 auto）与目标方言（默认 doris），粘贴 SQL 点"翻译"，右侧看到带复制按钮的译文代码块 + Markdown 报告（全自动/需人工统计、逐条 issue）。
2. 作为数据工程师，我想源方言自动探测失败或 SQL 非法时得到本地化警告，无 Traceback。
3. 作为数据工程师，我想展开"批量翻译目录"填目录（可选输出目录）得到批量报告；填了输出目录则译文按原结构写出（目录都在白名单内）。
4. 作为数据工程师，我想空输入/坏目录得到本地化提示（结构化 bad_dir，白名单前置）。
5. 作为数据工程师，我想翻译后展开"LLM 建议"点按钮得到针对"需人工"问题的 LLM 建议；未配 key 或无可建议项时得到本地化说明。
6. 作为 sql_review 用户，我想点"送到 transpile"跳转后 SQL 自动预填（localStorage 桥 `st_transpile_sql`）。
7. 作为中文/英文用户，我想 zh/en 全文案随全局开关切换；暗色模式配色正确。
8. 作为 API 用户，我想现有 `/translate`、`/batch`（无 out_dir 时）、`/dialects`、`/health` 契约不变，新增字段/端点向后兼容。
9. 作为维护者，我想有 Playwright 页测（TRP1-TRP9 等价，TRP6 LLM 用例以 no-key 结构化状态做确定性覆盖）与 i18n parity 测试。
10. 作为维护者，我想 Gradio ui.py、cases/transpile.yaml、catalog.py transpile 条目、page.py `.st-trp-*` 选择器、`_DATA_API_NAMES` 中的 sql_transpile 被干净清理。

## Implementation Decisions

- workspace `sql_transpile`（目录名 = manifest.name），vite base `/transpile/`；双栏布局与 Gradio 版一致（左控件/右结果），结果代码块参照 config_migrate ConfView（复制按钮）。
- 方言下拉数据来自 `GET /api/transpile/dialects`（已存在）。
- advice 端点为薄包装：服务端 transpile + advisable_issues + generate_advice；LLM 不可用的两种状态结构化返回，不在服务端渲染提示文案。
- `/batch` 的 out_dir：`check_path_allowed(out_dir)` 同白名单；响应报告与现状一致。
- manifest 切 external、hub 无条件挂 router；桥接 pickup 用 @shared/bridge.ts 现成键。
- 2 票：①workspace + 翻译/批量/建议全功能 + API 补齐 + cutover；②页测 + parity + 触点清理 + 批次收尾。

## Testing Decisions

- 既有缝：Playwright 页面层（先例 test_sqlfmt_page.py）、REST 契约层（test_sql_transpile.py 既有测试保持 + advice/out_dir 新测试）、i18n 资产层（先例 test_sqlfmt_i18n.py）。
- TRP6（LLM 建议）页测走 no-key 确定性路径；真 LLM 建议质量不进自动化。
- 桥接 pickup 页测：预置 localStorage 后加载页面断言预填（sql_review 页测先例）。

## Out of Scope

- transpiler/advisor/report 核心逻辑改动；其他页迁移；新功能。

## Further Notes

- page.py READY 路由 `"/transpile": ".st-trp-side"` 与 `.st-trp-main` 选择器随 YAML 退役一并清理。
- before 截图须在退役前截取。
