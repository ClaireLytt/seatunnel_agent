# 04: MCP Toolbox 工具描述补全 + 守卫测试

**What to build:** MCP Toolbox 页面的工具表格不再有空的 "What it does" 单元格:为 skew runtime / split-key 等缺描述的工具在注册处补一句话描述。页面表格与 MCP server 对外暴露的工具元数据同源(单一来源,UI 模块不维护手抄副本)。新增守卫测试:遍历已注册工具,任一缺描述即 fail,防止以后新工具无文档上线。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] pytest:registry 守卫测试断言每个注册的 MCP 工具描述非空(新测试,仿 tests/test_registry.py 的完整性检查风格)
- [ ] 真浏览器:/mcp 页面表格无空 "What it does" 单元格;截图留证
- [ ] `ruff check src tests scripts`、`mypy`、全量 `pytest` 绿(贴结尾输出)
