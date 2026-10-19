# 03: 免构建开发路径文档

**What to build:** 在 docs 写明日常前端迭代的 HMR 路径:`seatunnel-agent ui`(不带 --build)启动后端 + `npm run dev --workspace <name>` 起 Vite dev server(proxy 已配好指向后端),完全不走 build;并说明何时仍需 `--build`(批次验证/uitest 需真实构建产物)。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 文档包含两条命令的完整用法与适用场景边界
- [ ] 纯文档改动验证:`ruff check src tests` + `pytest --collect-only -q`
