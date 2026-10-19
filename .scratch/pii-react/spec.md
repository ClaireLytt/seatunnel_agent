# Spec: PII Scan React 迁移

Label: ready-for-agent

## Problem Statement

用户在 hub 的 `/pii` 页做敏感列扫描（扫 SQL 目录或粘贴 SQL，报告未脱敏
敏感列），但该页仍是 Gradio 实现（ui.py 155 行），与已迁移的 14 个 React
页不一致。

## Solution

按 docs/react_migration.md 触点清单，以 uitest 骨架 + metric_diff/
schema_drift 最新先例（含全部历批 fix-up 教训）迁移为 React，cutover 后
退役 Gradio 页及触点。REST `POST /api/pii/scan` 已 1:1 覆盖（sql/dir 二择）。
后端微调（既定模式）：bad_dir 结构化 {code,path}（白名单前置）+ 扫描异常
结构化降级 {code:"scan_failed",error}（旧页 ⚠️ parity），既有测试同步钉形状。

**流程约束**：全程在 `ui-build-incremental` 分支串行开发，不建新分支/worktree。

## User Stories

1. 作为数据工程师，我想填 SQL 目录（demo 预填 examples/pii_demo）、选方言点"扫描目录"，得到敏感列报告（命中规则、已/未脱敏、严重度）。
2. 作为数据工程师，我想展开"扫描粘贴的 SQL"贴 SQL 扫描单段。
3. 作为数据工程师，我想空目录/空 SQL/坏目录/扫描异常得到本地化提示（结构化错误），白名单外 403。
4. 作为中文/英文用户，我想 zh/en 全文案切换、暗色模式正确。
5. 作为 API 用户，我想 `/scan`、`/rules`、`/health` 成功契约不变。
6. 作为维护者，我想有 Playwright 页测（PII1-PII6 等价）与 i18n parity 测试（方言列表与 demo 预填钉定）；cases/pii.yaml、page.py `.st-pii-main` 回退、`_DATA_API_NAMES` 中的 pii_scan 干净清理（catalog/css 经查无触点）。

## Implementation Decisions

- workspace `pii_scan`（目录名 = manifest.name），vite base `/pii/`；
  schema_drift 参照（更简：单目录 + 单 SQL 折叠）。
- cutover：manifest 切 external、hub 无条件挂 router、_DATA_API_NAMES 移除。

## Testing Decisions

- 既有缝：Playwright 页面层（先例 test_metricdiff_page.py，demo
  examples/pii_demo）、REST 契约层（test_pii_scan.py 既有测试保持 + 错误
  形状钉定同步）、i18n 资产层（先例 test_metricdiff_i18n.py）。
- 页测覆盖 PII1-PII6 等价：demo 目录扫描（bank_card_no/未脱敏）、粘贴 SQL
  （手机号/列名+注释匹配）、已脱敏不升级、坏目录、干净 SQL 未命中、英文流程。

## Out of Scope

- scanner/rules 核心逻辑改动；其他页迁移；新功能。

## Further Notes

- i18n 的 result_label 键在旧布局中未使用——迁移时丢弃并在 parity 测试
  docstring 记录。before 截图须在退役前截取。
