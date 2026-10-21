# 03: shared vite 基座 manualChunks

**What to build:** makeViteConfig 内置 vendor 拆分(react/react-dom/recharts 等大依赖);25 workspace 全量 build,>500kB 警告消除(拆不掉的如实记录,不调阈值掩盖);抽 llmeval/llmcost/t2s 页测验证 dist 可服务。

**Blocked by:** None

**Status:** ready-for-agent

- [ ] 25 build 全绿且无 chunk 警告(或逐项记录残留)
- [ ] 抽样页测绿
