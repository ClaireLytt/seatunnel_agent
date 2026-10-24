# 01: seatunnel Demo 流程诚实化

**What to build:** 在 SeaTunnel Pipeline Builder 页点击 Demo 后,流程必须诚实:demo 的 config 写入目录守卫允许的路径(工作目录内),真正写成功;`validate_config` 对不存在的文件返回明确错误而不是 "Config is valid";最终总结由各工具真实结果推导——写入失败时总结必须说失败,不得宣称"已保存并验证通过"。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] pytest:对不存在路径调用 `validate_config` 返回错误(新测试,修复前红、修复后绿)
- [ ] pytest:demo 流程写入路径位于工作目录内且通过现有单一目录守卫(不新增第二套路径检查)
- [ ] 真浏览器:点 Demo,transcript 要么显示写入成功到允许路径,要么总结如实承认失败;截图留证
- [ ] `ruff check src tests scripts`、`mypy`、全量 `pytest` 绿(贴结尾输出)
