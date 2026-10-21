# 03: CI lint 覆盖全部前端 workspace

**What to build:** 每次 PR 时 CI 用单个 job 对全部 25 个前端 workspace 跑 eslint（`npm run lint --workspaces --if-present`），任何 workspace 的 lint 错误都会使 CI 失败；prettier 检查范围保持现状（uitest+shared），不做 matrix 化。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] lint workflow 的 frontend job 改为全 workspace lint，单 job 实现
- [ ] 本地执行同一命令验证当前仓库全部 workspace lint 通过（如有存量 lint 错误，修复或在报告中列为遗留问题由用户圈选）
- [ ] prettier 步骤保持不变
- [ ] 纯 CI/前端改动验证：`ruff check src tests` + `pytest --collect-only -q` 确认仓库未损坏
