# 02: 三处英文界面的中文串本地化

**What to build:** 英文界面下三处泄漏的中文串改为随 UI 语言渲染:Test Data Generator 的推断类型备注、Data Lineage 治理体检报告的标题/章节、Orchestrator 无 LLM 降级路由中的 agent 描述。中文界面保持原有中文,不回退。沿用现有 EN/中文按 `lang` 键选串的模式;agent 注册表为描述补英文版本,按语言取用。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] pytest:三处渲染函数分别断言 EN 与中文两种输出(新测试)
- [ ] 真浏览器:英文界面三处位置无中文、中文界面仍为中文;截图留证
- [ ] `ruff check src tests scripts`、`mypy`、全量 `pytest` 绿(贴结尾输出)
