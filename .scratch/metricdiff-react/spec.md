# Spec: Metric Consistency Check React 迁移

Label: ready-for-agent

## Problem Statement

用户在 hub 的 `/metricdiff` 页做指标口径一致性检查（扫描 SQL 目录找同名
指标的公式/来源冲突），但该页仍是 Gradio 实现（ui.py 115 行），与已迁移
的 13 个 React 页不一致。

## Solution

按 docs/react_migration.md 触点清单，以 uitest 骨架 + schema_drift 最新先例
（含全部历批 fix-up 教训）迁移为 React，cutover 后退役 Gradio 页及触点。
迄今最小页：单目录输入（demo 预填 examples/metricdiff_demo）+ 方言下拉 +
检查按钮 → Markdown 报告；REST `POST /api/metricdiff/check` 已 1:1 覆盖。
后端微调（既定模式）：bad_dir 结构化 {code,path}（白名单前置）+ 检查异常
结构化降级 {code:"check_failed",error}（旧页 ⚠️ parity）。

**流程约束**：全程在 `ui-build-incremental` 分支串行开发，不建新分支/worktree。

## User Stories

1. 作为数据工程师，我想填 SQL 目录（demo 预填）、选方言（7 种默认 hive）点"检查口径"，得到指标冲突 Markdown 报告（公式冲突/来源冲突，count(1)/count(*) 归一不误报）。
2. 作为数据工程师，我想空目录/坏目录得到本地化提示（结构化 bad_dir），白名单外 403，解析异常 ⚠️ 降级。
3. 作为中文/英文用户，我想 zh/en 全文案切换、暗色模式正确。
4. 作为 API 用户，我想 `/check`、`/health` 成功契约不变（错误 detail 形状为既定迁移模式）。
5. 作为维护者，我想有 Playwright 页测（MDF1-MDF5 等价）与 i18n parity 测试（含方言列表与 demo 预填钉定）；cases/metricdiff.yaml、page.py `.st-mdf-main` 回退、`_DATA_API_NAMES` 中的 metric_diff 干净清理（catalog/css 经查无触点）。

## Implementation Decisions

- workspace `metric_diff`（目录名 = manifest.name），vite base `/metricdiff/`；
  schema_drift 参照（更简：无双模式）。
- cutover：manifest 切 external、hub 无条件挂 router、_DATA_API_NAMES 移除。

## Testing Decisions

- 既有缝：Playwright 页面层（先例 test_schemadrift_page.py，demo
  examples/metricdiff_demo）、REST 契约层（test_metric_diff.py 既有测试保持
  + 错误形状断言同步）、i18n 资产层（先例 test_schemadrift_i18n.py）。
- 页测覆盖 MDF1-MDF5 等价：公式冲突、来源冲突+归一不误报、冲突引用文件名、
  坏目录、英文流程；另加空目录提示。

## Out of Scope

- checker/report 核心逻辑改动；其他页迁移；新功能。

## Further Notes

- 票据 2 张见 issues/；before 截图须在退役前截取。
