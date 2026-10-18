# Spec: Config Lint React 迁移

Label: ready-for-agent

## Problem

Config Lint（路由 `/conflint`）仍是 Gradio 页（`src/seatunnel_agent/agents/data/config_lint/ui.py`），
与已迁移的 6 个 React 页（uitest、config_migrate 等）视觉与工程结构不一致。

## Solution

按 `docs/react_migration.md` 13 点触点清单，以 `frontend/uitest` 骨架 +
最新先例 `frontend/config_migrate`（PR #126）为参照，新建 `frontend/config_lint`
workspace，功能 1:1 迁移后切 manifest external 并退役 Gradio 页。

约束：
- 全程在 `ui-build-incremental` 分支上串行开发，**不建新分支/worktree**。
- 功能 1:1：单配置 lint、目录批量 lint、zh/en i18n、暗色模式；不加新功能。
- REST 已存在（`api.py`: `POST /api/conflint/lint`、`GET /api/conflint/health`），
  前端直接复用；manifest `api=` 保持现状避免双挂载（按触点清单第 4 点核对）。

## User Stories

- 作为用户，我在 `/conflint` 看到与其他 React 页一致的界面：粘贴 HOCON 配置点
  "Lint 配置" 得到报告；展开"目录批量 Lint"输入目录（默认 `examples/conflint_demo`）
  点按钮得到批量报告。
- 作为用户，我切换 zh/en 与暗色模式时整页文案与配色正确。

## Tickets

1. `issues/01-workspace-lint-cutover.md` — React workspace + 单配置/目录 lint 全功能 + cutover 退役 Gradio
2. `issues/02-page-tests-i18n-cleanup.md` — Playwright 页面测试 + i18n parity + 触点清理收尾

## 验收

ruff / mypy / pytest 全绿 + uitest smoke + Playwright 页测 + 前后截图
（`docs/reports/shots/`）+ 批次报告落盘 `docs/reports/<YYYYMMDD>-conflint-react.md`
+ `python scripts/check_workflow.py` PASS。
