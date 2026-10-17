# 04: Stats 端点 + 客户端趋势图

**What to build:** 用户在页面底部看到历史审查统计趋势图（React 客户端渲染，替代 matplotlib）。新增只读 `GET /api/sql_review/stats` 端点供图表取数。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] GET /stats 返回历史统计（API 测试覆盖）
- [ ] React 趋势图渲染（CountsChart 风格）
- [ ] 无数据时有空态
