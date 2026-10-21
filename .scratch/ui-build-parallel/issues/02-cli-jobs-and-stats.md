# 02: CLI `--jobs` 参数与构建统计

**What to build:** 开发者可用 `seatunnel-agent ui --build --jobs N` 覆盖默认并发度；`--jobs` 不与 `--build` 联用时打印警告（与 `--force` 现有行为一致）。构建结束打印一行统计：built/skipped/failed 数量与总耗时，使加速效果可量化。

**Blocked by:** 01 并行构建核心

**Status:** ready-for-agent

- [ ] `--jobs N` 生效并传入构建函数；缺省为 `min(CPU核数, 6)`
- [ ] `--jobs` 单独使用时警告且不生效
- [ ] 构建结束输出 built/skipped/failed 计数与总耗时
- [ ] pytest 单测覆盖参数传递与统计输出
- [ ] 真机验证：`ui --build --force` 并行 vs `--jobs 1` 计时对比记录在批次报告
- [ ] ruff / mypy / pytest 通过
