# 01: ui --build 增量构建(hash 判定 + 跳过未变 workspace)

**What to build:** `seatunnel-agent ui --build` 逐 workspace 判定:对 workspace 源码/构建配置 + shared 源码计算内容 hash,与 `dist/.build-hash` 对比,一致则跳过构建;构建成功后写入新 hash。完全未改动时二次执行秒级完成;改 shared 则全部重建;dist 或 hash 文件缺失则重建。输出逐 workspace 报告 built/skipped。npm install 冷启动行为不变。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 首次构建:全部 workspace 构建并写 `dist/.build-hash`
- [ ] 无改动二次调用:全部跳过,不触发 npm build
- [ ] 改单个 workspace 源码:仅该 workspace 重建
- [ ] 改 shared 源码:全部 workspace 重建
- [ ] dist 或 hash 文件缺失:该 workspace 重建
- [ ] 测试经前端构建函数单一接缝(tmp 目录伪造 frontend + monkeypatch npm 调用),不真实执行 npm
- [ ] ruff/mypy + 定向测试通过
