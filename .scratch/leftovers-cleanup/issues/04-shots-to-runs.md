# 04: 页测截图输出迁 runs/ + 批次报告

**What to build:** 页测 SHOTS 常量统一指 runs/shots/;docs/reports/shots 历史 PNG 不动;react_migration.md 加"正式对比截图人为复制入 docs"约定;跑原本重写 PNG 的页测确认 git status 干净;全量验证 + 批次报告 + check_workflow(主会话收尾)。

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] grep docs/reports/shots 在 tests/ 零引用
- [ ] 跑 seatunnel/docqa 页测后 git status 干净
- [ ] 批次报告落盘;check_workflow PASS
