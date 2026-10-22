# Spec: Secret Scan 页迁移 React

Label: `ready-for-agent`

## Problem Statement

Secret Scan 是 devops 区仍停留在 Gradio 的页面之一（`agents/devops/secret_scan/manifest.py:16` 的 `render=` 仍指向 Gradio `ui.py`），与已迁移的 React agent 页（pii_scan、uitest、sql_review 等 25 个 workspace）视觉与交互不一致，且继续承担 Gradio 隐藏触发器、语言切换 hack 等历史包袱。用户要求按已重构的 ui agent 界面风格把 Secret Scan 迁到 React。

## Solution

按 `docs/react_migration.md` 清单迁移：新建 `frontend/secret_scan/` workspace（对标扫描类先例 pii_scan 的 App.tsx + api.ts + i18n.ts 结构，复用 @shared theme/组件/lang.ts），页面直接 fetch 现有 `POST /api/secretscan/scan`；manifest 切 `external=True, render=""`；随后退役 Gradio 旧页并迁移等价测试覆盖。

## User Stories

1. As a 开发者, I want Secret Scan 页与其他 React agent 页风格一致, so that 平台视觉统一
2. As a 开发者, I want 粘贴文本一键扫描并看到脱敏后的发现列表, so that 快速定位泄漏凭证
3. As a 开发者, I want 中英文随 st-lang cookie 切换, so that 与全站语言行为一致
4. As a 仓库维护者, I want 旧 Gradio 页触点全部清理（ui.py、uitest 用例、测试硬编码）, so that 不留死代码
5. As a 仓库维护者, I want 新页有 Playwright 页测与 i18n parity 测试, so that 回归可被发现

## Implementation Decisions

- 新 workspace 目录名 `secret_scan`（必须等于 manifest.name，datacompare 曾因目录名用路由名而挂载落空）；vite `base: '/secretscan/'`，dev proxy 指 `/api/secretscan`。
- REST 复用现有 `api.py` 的 `/scan`（内联文本），manifest 保留 `api=`。
- **目录扫描（假设，采纳推荐方案 A，用户未最终确认）**：Web 页只保留文本扫描；目录扫描在页面上以提示指向 CLI `seatunnel-agent secretscan`。不新增遍历目录的 API 端点（api.py 注释明确"API 不得遍历任意目录"的安全决定保持不变）。若用户选 B（白名单目录端点，复刻 CODEFIX_API_ALLOWED_DIRS 模式），票 01 范围相应扩大。
- i18n 从 `ui.py` 的 `_I18N` 字典逐字平移到 i18n.ts；后端渲染 key（report.py 的报告模板）留在 Python 侧。
- UI 规范：禁蓝紫渐变；按钮/图形优先，少解释文字（CLAUDE.md §2）。
- 开发分支：按用户明确指示在 `tkt/02-cli-jobs` 现分支继续（用户已确认接受与 ticket 02 混合的代价）。

## Testing Decisions

- 新增 `tests/test_secret_scan_page.py`：Playwright in-process uvicorn 模式（照 test_uitest_page.py），等价覆盖原 SEC1（密码赋值命中 + 页面不出现明文）；SEC2 目录扫描用例随方案 A 退役，改为文本用例覆盖高危规则。
- i18n parity 测试照 `tests/test_datacompare_i18n.py` 模式（解析 i18n.ts 逐键比对）。
- 退役清理断言：`tests/test_hub_pages.py:27` `_DEVOPS_ROUTES`、`tests/test_registry.py:17,37,43` 硬编码按现状更新。
- 验证按 CLAUDE.md §8：ruff / mypy / pytest / `pytest -m uitest tests/test_secret_scan_page.py` / uitest smoke / 截图前后对比（旧页截图用 git worktree 起迁移前 commit，`wait_until="load"`）。

## Out of Scope

- 其余 Gradio 页（ci_inspect / dep_check / doctor / release_notes）的迁移。
- secret_scan 扫描规则/报告格式改动（rules.py / scanner.py / report.py 不动）。
- 方案 B 的目录白名单端点（除非用户改选 B）。

## Further Notes

- 触点证据：uitest 用例 `ui_testing/cases/devops.yaml` SEC1/SEC2；`hub/css.py` 与 `ui_testing/catalog.py` 无 secretscan 专属条目（已核查）。
- 先例：pii_scan（扫描类 React 页）、sql_review 迁移批次报告 docs/reports/20261017-sqlreview-react-migration.md。
