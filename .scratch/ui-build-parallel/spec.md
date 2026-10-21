# Spec: ui --build 并行加速 + 前端 lint 全覆盖

Label: `ready-for-agent`

## Problem Statement

开发者运行 `seatunnel-agent ui --build` 时打开很慢。增量跳过机制已存在（内容哈希 vs `dist/.build-hash`），但冷构建 / 多 workspace 重建时 25 个 React workspace 顺序执行 `tsc -b && vite build`，串行耗时随 workspace 数线性增长（13 个 workspace 时冷构建已 71.3s）。改动 `frontend/shared` 任意一行会使全部 25 个 workspace 重建，串行代价尤其高。同时，CI 只对 uitest 一个 workspace 跑 lint/build，其余 24 个无 lint 覆盖。

## Solution

把 `_build_frontends` 中需要重建的 workspace 从串行改为有界并行执行（默认 `min(CPU核数, 6)`，`--jobs N` 可调），日志按 workspace 前缀区分，任一失败则整体失败并汇总失败清单；增量跳过与 `--force` 语义保持不变。CI 的前端 lint 从仅 uitest 扩展为单 job 一次性 lint 全部 workspace；并行逻辑在现有 pytest 套件中补充单测。

## User Stories

1. As a 前端开发者, I want 未改动的 workspace 继续被跳过（现状保留）, so that 日常只改一个页面时 `ui --build` 秒级启动
2. As a 前端开发者, I want 需要重建的多个 workspace 并行构建, so that 冷构建总耗时从 25×串行降到约 25/并发数
3. As a 前端开发者, I want 改动 shared 后触发的全量重建也走并行, so that shared 小改动不再等待漫长串行构建
4. As a 开发者, I want `--jobs N` 参数覆盖默认并发度, so that 可按机器性能调节资源占用
5. As a 开发者, I want 默认并发度为 `min(CPU核数, 6)`, so that 不手动配置也不会把机器打爆
6. As a 开发者, I want 并行日志按 workspace 名前缀区分, so that 交错输出仍可读
7. As a 开发者, I want 任一 workspace 构建失败时整体失败并列出所有失败 workspace, so that 一次运行就能看到全部问题
8. As a 开发者, I want 失败的 workspace 不写入 `.build-hash`, so that 下次运行会重试而不是误跳过
9. As a 开发者, I want `--force` 继续强制全量重建, so that 增量误判时有逃生门
10. As a 开发者, I want 跳过时仍打印 "skipped (unchanged)", so that 构建行为可见可审计
11. As a 仓库维护者, I want CI 用单 job 跑全部 workspace 的 eslint, so that 24 个无覆盖的 workspace 的 lint 问题在 PR 阶段被拦截
12. As a 仓库维护者, I want 并行构建逻辑有 pytest 单测（monkeypatch npm，不跑真实构建）, so that 回归可被快速发现
13. As a 仓库维护者, I want 构建结束打印总耗时与 built/skipped/failed 统计, so that 加速效果可量化验证

## Implementation Decisions

- 改动集中在 CLI 核心模块的 `_build_frontends`：哈希计算与跳过判断逻辑不变；把"需要构建"的 workspace 收集成列表后用有界线程池并行调用 `npm run build --workspace <name>`（npm 子进程本身释放 GIL，线程池足够，不需 multiprocessing）。
- `ui` 命令新增 `--jobs N` 选项，默认 `min(os.cpu_count(), 6)`；仅与 `--build` 联用，单独使用时警告（与现有 `--force` 行为一致）。
- 并行期间每个子进程输出捕获后按 `[workspace] ` 前缀整体刷出（避免行级交错）；任一失败收集后统一报错退出，退出码非零。
- 成功的 workspace 照旧写 `.build-hash`；失败的不写。
- shared 失效粒度不做优化（语义正确，Q8 决定保持现状）。
- CI lint 扩展：lint workflow 的 frontend job 改为 `npm run lint --workspaces --if-present` 单 job 全量；prettier 检查范围保持现状（uitest+shared）。
- 不引入 turborepo/nx 等外部构建编排工具（Q2 决定）。
- 不把 lint 塞进 `ui --build` 运行时流程（Q3 决定，避免拖慢启动）。
- 假设（用户未明确确认，采纳推荐答案）：Q7 并发度方案、Q8 保持 shared 失效现状、Q9 单 job CI lint。

## Testing Decisions

- 只测外部行为：给定 fake frontend 树与 monkeypatch 的 npm 调用记录，断言哪些 workspace 被构建/跳过、失败如何汇总、`.build-hash` 是否写入；不断言内部线程调度细节。
- 测试缝沿用现有唯一缝 `_build_frontends(frontend=..., force=...)`（新增 `jobs=` 参数），npm 子进程 monkeypatch，先例即现有的 incremental 构建测试模块（13 个用例的 fake frontend + npm_calls fixture 模式）。
- 新增用例：多 workspace 并行时全部被构建且并发数不超过 jobs 上限；一个 workspace 失败时其余完成、整体报错、失败者无 `.build-hash`；`--jobs 1` 退化为串行等价行为。
- 验证命令按 CLAUDE.md 第 8 节：ruff / mypy / pytest；真实效果用 `seatunnel-agent ui --build --force` 前后计时对比。

## Out of Scope

- shared 变更的细粒度失效/依赖图分析。
- 构建产物缓存共享（远端缓存、tsbuildinfo 跨 workspace 复用）。
- vite dev 模式开发流（已有 docs/frontend_dev.md）。
- prettier 检查范围扩大、CI matrix 化。
- hub 启动后页面加载性能（Q1 判定慢点在构建阶段）。

## Further Notes

- 现状冷构建基准：13 workspace 时 71.3s（docs/reports 旧报告），现 25 个 workspace；预期并行 6 路后冷构建降至约 1/4–1/5。
- 磁盘上多数 workspace 当前缺 `.build-hash`，首次运行本方案后即全部建立，后续日常运行以跳过为主。
