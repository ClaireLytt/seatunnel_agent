# Spec: `seatunnel-agent ui --build` 增量构建

Label: ready-for-agent

## Problem Statement

前端开发者每次改完 frontend 代码后用 `seatunnel-agent ui --build` 验证页面,该命令对全部 5 个可构建 workspace 串行全量执行 `tsc -b && vite build`,即使只改了一个 workspace(甚至一个都没改)也要等几分钟,日常开发循环被构建时间拖慢。

## Solution

`--build` 默认变为增量:对每个 workspace 计算其源码与构建配置(含 shared 包源码)的内容 hash,与上次构建时写入 dist 的 hash 对比,一致则跳过该 workspace 的构建。新增 `--force` 标志强制全量重建。同时在文档中写明"后端 + vite dev server"的免构建日常开发路径。

## User Stories

1. As a 前端开发者, I want `ui --build` 跳过未改动的 workspace, so that 只改一个页面时不用等全部 workspace 重建。
2. As a 前端开发者, I want 完全未改动时第二次 `ui --build` 秒级完成, so that 反复重启验证的成本接近零。
3. As a 前端开发者, I want 改了 shared 包后所有依赖它的 workspace 都自动重建, so that 不会拿到过期的构建产物。
4. As a 前端开发者, I want 一个 `--force` 标志, so that 怀疑缓存不对时可以一键全量重建兜底。
5. As a 批次验证执行者, I want 增量判定基于文件内容 hash 而非 mtime/git 状态, so that git checkout、stash 等操作不会造成误判。
6. As a 前端开发者, I want 跳过与重建的 workspace 在命令输出中明示, so that 我清楚本次实际构建了什么。
7. As a 新 clone 仓库的开发者, I want 首次 `ui --build` 行为与现在一致(npm install + 全量构建), so that 增量逻辑对冷启动透明。
8. As a 日常开发者, I want 文档写明 `seatunnel-agent ui` + `npm run dev --workspace <name>` 的 HMR 路径, so that 迭代 UI 时可以完全不走 build。
9. As a 维护者, I want hash 文件存放在 dist 内并随 dist 删除而失效, so that 手动删 dist 后必然重建,无需额外失效机制。

## Implementation Decisions

- 修改 CLI `ui` 命令的前端构建函数:由单次 `npm run build --workspaces --if-present` 改为逐 workspace 判定并构建(`npm run build --workspace <name>`),无 build 脚本的 workspace(shared)仍跳过。
- 增量判据:workspace 的 `src/`、`package.json`、`vite.config.ts`、`tsconfig*` 加 shared 包源码,计算内容 hash,与 `dist/.build-hash` 对比;一致即跳过。shared 的 hash 纳入每个 workspace 的判定输入,shared 变则全部重建。
- hash 采用文件内容摘要(与 git 工作区状态、mtime 解耦);写入时机为该 workspace 构建成功之后。
- CLI 语义:`--build` 默认增量;新增 `--force`(与 `--build` 连用)强制全量;dist 缺失或 hash 文件缺失视同需要重建。
- `node_modules` 缺失时先 `npm install` 的现有行为保持不变。
- 构建输出逐 workspace 报告 built/skipped。
- dev 模式不进 CLI,仅文档化既有的 vite dev + proxy 路径(proxy 已配置指向后端端口)。
- hub 启动段(全量 import agent ui 模块)不在本 spec 范围,记为遗留问题。

## Testing Decisions

- 只测外部行为:通过前端构建函数这一单一接缝测试,在 tmp 目录伪造 `frontend/` workspace 结构,monkeypatch npm 子进程调用,断言"哪些 workspace 被触发构建"。不测 hash 计算内部函数。
- 覆盖:首次全部构建并写 hash;无改动二次调用全部跳过;改单个 workspace 仅其重建;改 shared 全部重建;force 全部重建;dist/hash 缺失时重建。
- CLI 层仅补 `--force` 标志透传的轻量测试,复用仓库现有 click CLI 测试先例。
- 不在单元测试中真实执行 npm/vite;真实构建效果由批次收尾的 `ui --build` 连跑计时 + uitest smoke 验证。

## Out of Scope

- hub 启动时 agent ui 模块的惰性加载(遗留问题,单独评估)。
- `ui --dev <workspace>` CLI 封装(文档先行,有需要再做)。
- 并行构建多个 workspace、引入 turbo/nx 等构建编排工具。
- vite/tsc 本身的构建加速调优。

## Further Notes

- 第二次连跑 `ui --build` 的耗时对比(改动前后)作为批次报告的差异证据。
- 既有 `tsc -b` 的 `.tsbuildinfo` 增量与本方案叠加,互不冲突。
