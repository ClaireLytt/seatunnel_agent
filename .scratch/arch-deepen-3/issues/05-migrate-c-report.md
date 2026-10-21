# 05: D1 migrate C — 余 7 页 + 批次报告

**What to build:** 收尾 pii_scan/schema_drift/seatunnel/sql_testgen/sql_transpile/uitest/text2sql;两处漂移 header 归一并记录;grep 证明旧 header 长串/独立 i18n init/两种错误形状零残留(正当保留项如实列出);全量验证 + 批次报告 + check_workflow(主会话收尾)。

**Blocked by:** 02(惯例接 04 后)

**Status:** ready-for-agent

- [ ] grep 证据;全量 ruff/mypy/pytest + uitest smoke 绿
- [ ] 批次报告落盘;check_workflow PASS
