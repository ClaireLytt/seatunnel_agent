# Deepening: 页测夹具工厂 + 前端脚手架工厂(C1+C2)

Labels: `ready-for-agent`
Branch: `plat`(沿用:直接在 plat 开发提交,不切新分支)

## Problem Statement

React 迁移波(25 个 workspace)留下两大浅模块群:① 25 个 `tests/test_*_page.py` 各自复制 `_free_port`/uvicorn `page_url` fixture/`_zh_page`(≈1,200 行,差异只有 manifest/router/挂载路径/个别 env);② 每个 workspace 10 份脚手架文件(vite.config/tsconfig×3/eslint/tailwind/postcss/index.html/main.tsx/vite-env,≈3,500 行,vite 差异仅 base/apiPath 两参数,tsconfig 三件套逐字节相同)。改一处启动逻辑或构建选项要摸 25 个文件;每个新页面的迁移票都要复制一遍。

## Solution

两个深模块,各自收敛一群浅模块:① conftest 提供 `make_page_url(...)` 工厂与 `zh_page` helper,页测文件的夹具收敛为一行声明;② `frontend/shared` 提供 `makeViteConfig({base, apiPath})` 与可 `extends` 的 tsconfig/可 re-export 的 eslint/tailwind/postcss 基座,workspace 脚手架从 141 行降到数个 2 行文件。行为零变化:同样的测试过、同样的构建产物。

## User Stories

1. As a maintainer, I want the uvicorn page-test fixture implemented once in conftest, so that changing startup logic (timeout, port policy, skip message) fixes all 25 test files at once
2. As a migration author, I want a one-line `page_url` declaration per page-test file, so that the next page's ticket carries no fixture boilerplate
3. As a maintainer, I want `_zh_page`/st-lang cookie handling shared, so that locale-chrome testing is uniform
4. As a test author, I want per-test env neutralization (keys/settings-store/dotenv) available as fixture options, so that deterministic no-key paths don't re-derive the three-monkeypatch recipe
5. As a frontend maintainer, I want one `makeViteConfig({base, apiPath})` factory, so that a vite upgrade or proxy change lands in one file
6. As a frontend maintainer, I want workspace tsconfigs to `extends` a shared base, so that compiler-option drift across 25 copies is impossible
7. As a frontend maintainer, I want eslint/tailwind/postcss configs re-exported from shared, so that lint/style policy is single-sourced
8. As a migration author, I want new-workspace scaffolding to be ~4 two-line files, so that future page tickets skip the copy step
9. As a reviewer, I want zero behavior change, so that the full pytest suite and all 25 workspace builds are the complete regression
10. As a developer, I want the deep modules' own behavior (port allocation, dist-missing skip, config factory output) covered by tests at their interfaces, so that regressions are caught at one seam

## Implementation Decisions

- C1(测试夹具):conftest 新增工厂——接口形状 `make_page_url(manifest, router, mount, *, env: dict | None = None, neutralize_llm: bool = False, chdir_tmp: bool = False)` 返回 pytest fixture;`zh_page(ctx_factory, page_url)` helper 同址共享。各 test_*_page.py 删本地 `_free_port`/`page_url`/`_zh_page`,改一行声明;文件内特有 env(如 CODEFIX_API_ALLOWED_DIRS 留空、LLM_USAGE_PATH 指 demo)经 `env=`/开关参数表达
- 迁移方式:expand–contract——先落共享工厂(expand),分批把 25 个页测文件切过去(migrate,按 5–8 文件一批跑 `-m uitest` 定向验证),最后无调用者时无需 contract(本地副本随迁移即删)
- C2(脚手架):`frontend/shared/vite.base.ts` 导出 `makeViteConfig({ base, apiPath })`(封装 react 插件、@/@shared alias、dev proxy → 7860、outDir);`frontend/shared/tsconfig.base.json`/`tsconfig.app.base.json`/`tsconfig.node.base.json` 供 `extends`;eslint/tailwind/postcss 基座从 shared re-export;index.html/main.tsx 保留每 workspace 一份(title 真差异、入口文件 vite 约定),不强行收敛
- C2 迁移同样 expand–contract:先落基座,分批切 workspace(每批 lint+build 全绿),批间 CI 始终绿(旧 inline 配置仍可用)
- 行为零变化为硬约束:C1 以全量 pytest + 全部 `-m uitest` 页测为验收;C2 以 25 个 workspace `npm run build` 产物可服务 + lint 全绿为验收
- 不动:各页测的领域断言、各 workspace 的 index.html title、i18n resources、安全门 env——这些是真实差异,不是重复
- C3(PageHeader/useRunner)、C4(hub/sse.py)、C5(initI18n/postJSON)、C6(shot_old 清理)不在本 spec,另行立项

## Testing Decisions

- 只测外部行为:C1 的工厂本身不单测内部,由 25 个页测文件通过它跑通即是验收(接口即测试面);另加一个最小自测(dist 缺失 → skip、端口可分配)
- C2 的"测试"= 构建:每批 workspace `npm run lint` + `npm run build`;抽查 1–2 个 dist 在 in-process uvicorn 页测下仍可服务(已有页测覆盖)
- 先例:conftest 既有共享 fixture(download_text/_no_llm_usage_log);uitest 页测 25 个文件即回归网
- 全量验证:ruff/mypy/pytest、pytest -m uitest(全部页测)、uitest smoke --no-llm、check_workflow.py

## Out of Scope

- C3/C4/C5/C6 候选;任何生产代码行为变化;index.html/main.tsx 的强行收敛;页测领域断言改写
- main 操作、新分支、PR

## Further Notes

- 依据:架构评审报告(C:\Users\Lenovo\AppData\Local\Temp\architecture-review-20261021.html)与探查量化(脚手架 ~3,500 行、夹具 ~1,200 行;vite diff 仅 2 参数、tsconfig 逐字节相同)
- 与八个待批退役票并行不冲突(退役票只删 Gradio ui 模块,不碰页测夹具/脚手架;若退役先行,迁移批次自动少几个文件)
- 仓库尚无 GLOSSARY.md;若实施中需命名新概念(如 "workspace scaffold base")再按 domain-modeling 流程建档
