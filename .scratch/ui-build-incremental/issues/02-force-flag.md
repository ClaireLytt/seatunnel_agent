# 02: `--force` 强制全量重建标志

**What to build:** `seatunnel-agent ui --build --force` 忽略 hash 判定,全部 workspace 重建。用户怀疑缓存不对时一键兜底。

**Blocked by:** 01 (增量构建)

**Status:** ready-for-agent

- [ ] `--force` 时所有 workspace 均重建,并写入新 hash
- [ ] 接缝测试覆盖 force 路径
- [ ] CLI 层 `--force` 标志透传轻量测试(复用现有 click CLI 测试先例)
- [ ] ruff/mypy + 定向测试通过
