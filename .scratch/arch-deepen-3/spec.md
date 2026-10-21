# Deepening: 前端骨架四件套 + worktree 安全清理(D1+D2)

Labels: `ready-for-agent`
Branch: `dev`(假设:沿用"在当前分支直接开发提交";如需改分支请指出)

## Problem Statement

① 25 个 React workspace 的 App 骨架是复制粘贴后已各自漂移的浅模块群:header 块 25/25 逐字(2 份已漂移字号/宽度)、running 三元 ×23、`⚠️` catch 样板 24 处、空态门控每页手写;i18next init 骨架逐字 ×25;fetch 错误处理 22/25 份且 shared api 模块注释自述两种错误形状并存。改一处样式要摸 25 个文件,且 ci_inspect 第 26 个 workspace 的规划已 ready-for-agent——不先收敛就会再+1 份全套复制。
② 2026-10-22 误删仓库事故(grep 子串误匹配主仓库 + 静默守卫 + rm 回退)后的清理规则只写在 CLAUDE.md,文档挡不住下一次手滑:scripts/ 下没有实现"逐个 remove、前缀白名单、禁回退"的工具。

## Solution

① @shared 落四个深模块并分批迁 25 页:PageHeader(badge/标题/副标题/home 链接)、useRunner(busy/error/report 状态机 + catch 归一 + zh/en 归一)、initI18n(resources)、fetchJson(统一抛 ApiError,两种错误形状并一);顺带把按钮 Tailwind 长串收敛进共享常量。行为与外观零变化。
② scripts/ 新增 worktree 安全清理深模块:枚举 → resolve 后必须满足 `.claude/worktrees/agent-` 完整前缀 → 逐个 `git worktree remove`(失败即整体非零退出,绝无 rm/Remove-Item 回退)→ 默认 dry-run,`--yes` 才执行;事故场景(主仓库路径含 "agent")写成单测固化。

## User Stories

1. As a frontend maintainer, I want the page header implemented once, so that a style change lands on all 25 pages at once instead of drifting per copy
2. As a frontend maintainer, I want the two already-drifted headers re-unified by the shared component, so that visual consistency is restored
3. As a page author, I want useRunner to own busy/error/result state and the ⚠️ catch, so that a new page writes only its domain form and render
4. As a page author, I want initI18n(resources), so that each page's i18n file is just its dictionaries
5. As a page author, I want fetchJson to raise one ApiError shape, so that error handling is uniform and the two legacy shapes disappear
6. As a migration author, I want the upcoming ci_inspect workspace to start on these deep modules, so that the 26th page carries zero skeleton boilerplate
7. As a reviewer, I want zero behavior/visual change on the 25 migrated pages, so that lint/build/page tests remain the complete regression
8. As any future session, I want one safe worktree-cleanup entry point, so that nobody hand-writes destructive shell again
9. As a repo owner, I want the cleanup tool to refuse any path outside the agent-worktree prefix (resolved, not substring-matched), so that the main repo can never be matched
10. As a repo owner, I want guard failures to fail the whole run loudly with no deletion fallback, so that the 2026-10-22 failure mode is structurally impossible
11. As a repo owner, I want dry-run as the default and an explicit --yes, so that the destructive step always shows its full target list first
12. As a developer, I want the incident scenario covered by unit tests, so that the rule lives in executable code, not only in CLAUDE.md

## Implementation Decisions

- D1 四深模块进 frontend/shared(components/PageHeader、useRunner hook、i18n 的 initI18n、api 的 fetchJson);PageHeader 接口最小:{badge, maxW?} + 标题/副标题走 i18n keys(title/subtitle 惯例已统一);useRunner 返回 {busy, error, result, run};按钮长串入 constants(btnPrimary/btnGhost)
- 迁移走 expand–migrate:先落共享件 + 2 试点页(小表单页 doc_qa/issue_triage),再按 8/8/7 三批切其余 23 页;两处已漂移 header 以共享件形状为准归一(字号 text-4xl、宽度按多数派),差异记录在报告
- fetchJson 收敛错误形状为 ApiError{status, detail};12 份 code/path 形状的调用点随批改写;shared api 模块中"两形状并存"注释随之删除
- 行为零变化为硬约束(漂移归一除外,属恢复一致性);每批 lint+build+定向页测
- D2:scripts/cleanup_worktrees.py——枚举 `git worktree list --porcelain`;白名单判定用 Path.resolve 后的完整前缀比较(`<repo>/.claude/worktrees/agent-`),禁止子串匹配;逐个 `git worktree remove <path>`(先不 --force;失败收集并整体退出非零,打印未删清单);任何分支都不含 rm/Remove-Item/ignore-errors;默认 dry-run 打印完整目标清单,--yes 才执行;结尾 `git worktree prune` 仅在全部成功后
- D2 不改 CLAUDE.md 规则本身;工具落地后在 §9 末尾加一行指向该脚本(清理只用此入口)
- 批次:D2 一票先行(小);D1 expand+试点 → migrate ×3 批;D1/D2 文件不相交可并行

## Testing Decisions

- D1 缝全部既有:25 workspace `npm run lint`+`npm run build`;定向页测按批跑(先例 C1/C2 迁移波);PageHeader/useRunner 不做组件单测,由页测冒烟(h1/home/⚠️)转化为对共享件的一次性覆盖
- D2 新模块以接口测:pytest 单测——主仓库路径含 "agent" 不入选、前缀外路径拒绝、dry-run 不执行、remove 失败→非零退出且无删除回退(subprocess 以临时 git 仓库+真实 worktree 跑,先例 tests/test_code_fix.py 的 make_project 临时仓库夹具)
- 全量验证:ruff/mypy/pytest、uitest smoke、check_workflow.py

## Out of Scope

- D3(后端 sse_stream)、D4(余 5 页测迁工厂)、D5(hub/css.py);ci_inspect 迁移本身(另一条在途规划)
- 页面视觉改版;CLAUDE.md §9 规则改写;main 操作、新分支、PR 流程(ship 时另说)

## Further Notes

- 证据:第二轮评审报告(architecture-review-20261022.html)与探查量化(header 25/25、catch ×24、init ×25、`def _sse(` ×8 等);shared api 两形状注释为接口漂移活证据
- 时间窗:ci_inspect 规划(.scratch/ci-log-triage-react)已 ready-for-agent,D1 应先于它落地
- 仓库无 GLOSSARY.md;若实施中固化新术语(如 "runner"),按 domain-modeling 建档
