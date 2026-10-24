# 06: secretscan 匹配带前缀的密码赋值

**What to build:** Secret Scan 能标记形如 `db_password = "SuperSecret123!"`、`mysql_password: '…'`、`root_pwd = "…"` 的带前缀密码赋值(标识符以 password/passwd/pwd 结尾),同时保持现有长度阈值与占位符过滤不变——示例/占位值(如 changeme 类)不得因此误报。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] pytest 正例:`db_password = "SuperSecret123!"` 被标记为 password_assign(新测试,修复前红、修复后绿)
- [ ] pytest 反例:占位符样例仍不被标记(新测试)
- [ ] 真浏览器:/secretscan 页粘贴正例文本,findings 中出现该条且预览 masked;截图留证
- [ ] `ruff check src tests scripts`、`mypy`、全量 `pytest` 绿(贴结尾输出)
