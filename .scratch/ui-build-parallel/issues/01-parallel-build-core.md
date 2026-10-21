# 01: 并行构建核心——有界线程池 + 失败汇总

**What to build:** 开发者运行 `ui --build` 时，所有需要重建的 workspace 以有界并发（默认 `min(CPU核数, 6)`）并行执行 npm build，总耗时从串行累加降为约 1/并发数；增量跳过与 `--force` 行为完全不变。每个 workspace 的构建输出整块带 `[name] ` 前缀刷出；任一失败则整体以非零退出并汇总列出全部失败 workspace，失败者不写入构建哈希（下次必重试）。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 多个待重建 workspace 并行构建，同时在跑的构建数不超过并发上限
- [ ] 未变 workspace 照旧打印 "skipped (unchanged)" 且不进线程池
- [ ] 一个 workspace 失败时其余继续完成，整体报错并列出失败清单
- [ ] 失败 workspace 不写 `.build-hash`，成功者照旧写
- [ ] 构建函数新增并发参数，并发=1 时行为与现有串行等价
- [ ] pytest 单测覆盖以上行为（沿用 fake frontend + monkeypatch npm 的现有缝，不跑真实 npm）
- [ ] ruff / mypy / pytest 通过
