# 03: Text2SQL 查询日志 Question 必填

**What to build:** Text2SQL 查询日志的每条新记录都带非空的 question 字段:聊天路径写用户原始问题;非聊天通道(MCP 工具调用、订阅任务)沿用现有 `[mcp] …` / `[subscription] …` 带通道标签的约定,绝不写空串。History 页对历史遗留的空行显示 "—" 占位而不是空白(不回填旧数据)。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] pytest:查询日志每个写入路径(chat / MCP / subscription)产出的记录 question 非空(新测试)
- [ ] 真浏览器:History 标签页新产生的行均有 Question;旧空行显示 "—";截图留证
- [ ] `ruff check src tests scripts`、`mypy`、全量 `pytest` 绿(贴结尾输出)
