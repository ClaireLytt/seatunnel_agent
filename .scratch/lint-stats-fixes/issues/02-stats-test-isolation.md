# 02: sql_review stats 页测隔离

**What to build:** test_sql_review_page 的 stats 刷新测试在任何机器确定性通过:fixture 把 review 历史的读取路径隔离到 tmp(查 ReviewLogger/其日志类的 env 对,仿 JsonlLog 惯例;以代码为准),替换"只打桩写入端"的做法;断言与端点逻辑不动。

**Blocked by:** None(与 01 文件不相交,顺序执行)

**Status:** ready-for-agent

- [ ] 本机(有真实 review 历史)`pytest -m uitest tests/test_sql_review_page.py` 全绿
- [ ] ruff/mypy 绿;收尾全量验证 + 批次报告 + check_workflow(主会话)
