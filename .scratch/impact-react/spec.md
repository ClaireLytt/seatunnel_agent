# Spec: Change Impact Analysis React 迁移

Label: ready-for-agent

## Problem Statement

用户在 hub 的 `/impact` 页做 SQL 变更影响分析（两份 SQL 目录或两段粘贴
SQL 的血缘 diff + 下游波及 + 严重度分级图），但该页仍是 Gradio 实现
（ui_impact.py 234 行），是 data 工作区 lineage 包里最后的 Gradio 页。

## Solution

按 docs/react_migration.md 触点清单，以 uitest 骨架 + **frontend/data_lineage
先例**（GraphView/mermaid npm 直接复用，含其 fix-up 教训：结构化+本地化
守卫、暗色 mermaid 主题）迁移为 React，cutover 后退役 Gradio 页及触点。

**REST 补齐**（可加性，核心零改动）：`POST /api/lineage/impact` 响应增加
`mermaid`（severity 着色图，复用 render_impact_mermaid，/sla_impact 先例）
与 paste 模式的 `sql_diff`（复用 render_text_diff）；目录校验白名单前置 +
结构化 bad_dir。既有响应字段不变（现有 API 测试全部保持）。

**流程约束**：全程在 `ui-build-incremental` 分支串行开发，不建新分支/worktree。

## User Stories

1. 作为数据工程师，我想在"目录模式"页签填旧/新 SQL 目录点"分析"，得到严重度着色的 Mermaid 影响图（error/warn/info/blast 灰）+ Markdown 报告（[error|warn|info] 分级明细）。
2. 作为数据工程师，我想在"粘贴 SQL"页签贴旧/新 SQL（可选上下文目录做全仓下游波及），报告末尾附 SQL diff 代码块。
3. 作为数据工程师，我想两个页签共享方言下拉（默认 hive）与下游深度滑杆（1-10，默认 3），深度=1 时报告按截断展示。
4. 作为数据工程师，我想缺目录/缺 SQL/坏目录得到本地化提示（结构化错误），白名单外目录 403。
5. 作为中文/英文用户，我想 zh/en 全文案切换（报告服务端按 lang 渲染）、暗色模式下 mermaid 随主题。
6. 作为 API 用户，我想 `/api/lineage/impact` 既有字段不变，`mermaid`/`sql_diff` 为新增可加字段。
7. 作为维护者，我想有 Playwright 页测（IMP1-IMP8 等价）与 i18n parity 测试；cases/impact.yaml、scroll SCR3、catalog/page.py/asserts.py/css.py 的 `.st-imp-*` 触点干净清理；lineage 包随之无 Gradio（`mermaid_html` iframe 模板等 Gradio-only 残留一并退役）。

## Implementation Decisions

- workspace `change_impact`（目录名 = manifest.name），vite base `/impact/`；
  GraphView/ReportView 从 data_lineage 复制（mermaid npm 锁同版本，节点
  点击回调本页不需要——impact 图无跳转语义，复制时去掉 onNode）。
- 双页签用轻量 tab 按钮组（@shared token 样式），dialect/depth 控件置于
  页签下方共享（1:1 布局）。
- API 一个端点不拆分：响应增加 mermaid 恒有、sql_diff 仅 text 模式;
  bad_dir 结构化 {code,message}；history source 标签统一为 "api"
  （UI 经 REST 调用,旧 "ui" 标签随 Gradio 退役,记录于报告差异节）。
- cutover：manifest 第二条目切 external=True、render=""；hub 的 lineage
  router 已无条件挂载（上批），无需新增挂载；删除 ui_impact.py 与
  render.py 的 mermaid_html/_MERMAID_HTML_TEMPLATE（含 __init__ 导出与
  其单测迁移/删除）。

## Testing Decisions

- 既有缝：Playwright 页面层（先例 test_lineage_page.py，demo 数据
  examples/impact_demo）、REST 契约层（test_lineage_impact.py 既有测试
  保持 + mermaid/sql_diff 可加字段断言）、i18n 资产层（先例
  test_lineage_i18n.py）。
- 页测覆盖 IMP1-IMP8 等价：目录模式严重度文本、坏目录提示、粘贴模式
  SQL diff、缺 SQL 提示、上下文目录波及、深度=1 截断、英文全流程。

## Out of Scope

- impact.py 分析核心改动；git 模式/MCP 工具；其他页迁移；新功能。

## Further Notes

- 票据 2 张见 issues/；before 截图须在退役前截取。
- css/page/asserts 清理后 `.st-imp-*` 应零残留（data 工作区自此只剩
  /loginspect /mcp /pii /schemadrift /dagcheck /metricdiff 为 Gradio）。
