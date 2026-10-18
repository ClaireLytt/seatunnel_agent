# Spec: Schema Drift Check React 迁移

Label: ready-for-agent

## Problem Statement

用户在 hub 的 `/schemadrift` 页做表结构漂移检查（粘贴新旧 DDL 或对比两个
目录），但该页仍是 Gradio 实现（ui.py 166 行），与已迁移的 13 个 React 页
不一致。

## Solution

按 docs/react_migration.md 触点清单，以 uitest 骨架 + sql_fmt/change_impact
先例（含历批 fix-up 教训）迁移为 React，cutover 后退役 Gradio 页及触点。
纯确定性页：REST 零缺口（两个回调都映射到现成 `POST /api/schemadrift/diff`，
report=true 取 Markdown）。唯一后端微调：目录错误对齐既定模式——白名单
前置（已有）+ bad_path 结构化 {code,path}（可加性，现有 400 文本改形状，
既有测试同步）。

**流程约束**：全程在 `ui-build-incremental` 分支串行开发，不建新分支/worktree。

## User Stories

1. 作为数据工程师，我想选方言（7 种，默认 hive）、粘贴旧/新 DDL 点"对比"，得到漂移 Markdown 报告（删列/类型变宽/疑似改名等）。
2. 作为数据工程师，我想展开"对比两个目录"（预填 examples/schema_drift_demo/old|new）点按钮得到目录级漂移报告。
3. 作为数据工程师，我想空输入/半填/坏路径得到本地化提示（结构化 bad_path），白名单外路径 403。
4. 作为中文/英文用户，我想 zh/en 全文案切换、暗色模式正确。
5. 作为 API 用户，我想 `/diff`、`/health` 既有成功契约不变（bad_path detail 形状变化为既定迁移模式，记录于报告差异节）。
6. 作为维护者，我想有 Playwright 页测（SDF1-SDF6 等价）与 i18n parity 测试；cases/schemadrift.yaml、page.py `.st-sdf-main` 回退、`_DATA_API_NAMES` 中的 schema_drift 干净清理（catalog/css/scroll 经查无触点）。

## Implementation Decisions

- workspace `schema_drift`（目录名 = manifest.name），vite base `/schemadrift/`；
  sql_fmt 参照（方言下拉 + 双 textarea + 目录折叠区 + ReportView）。
- 目录默认值在前端复刻（SDF1 依赖）。
- cutover：manifest 切 external、hub 无条件挂 router、_DATA_API_NAMES 移除。
- 方言列表硬拷贝加 parity 测试钉定（change_impact fix-up 教训）。

## Testing Decisions

- 既有缝：Playwright 页面层（先例 test_sqlfmt_page.py，demo 数据
  examples/schema_drift_demo）、REST 契约层（test_schema_drift.py 既有测试
  保持 + bad_path 形状断言同步）、i18n 资产层（先例 test_sqlfmt_i18n.py）。
- 页测覆盖 SDF1-SDF6 等价：目录 demo 对比、粘贴 DDL 漂移、无漂移、疑似
  改名、坏路径、英文流程；另加空输入提示。

## Out of Scope

- differ/report 核心逻辑改动；其他页迁移；新功能。

## Further Notes

- 票据 2 张见 issues/；before 截图须在退役前截取。
