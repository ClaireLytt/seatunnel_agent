# 01: text2sql lint 修复

**What to build:** text2sql workspace lint 恒绿:BoardsView 4 处与 SubscriptionsView 1 处 no-explicit-any 换真实类型(复用 api 层类型);MetricsView 回调内的 useMetric 调用重构为 rules-of-hooks 合规等价实现(行为/外观不变);1 条警告消除。build 产物等价,页测与聊天 API 测试回归不动。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] npm run lint --workspace text2sql → 0 errors 0 warnings
- [ ] npm run build --workspace text2sql → 绿
- [ ] pytest tests/test_t2s_chat_api.py -q 回归绿;pytest -m uitest tests/test_t2s_page.py 绿
