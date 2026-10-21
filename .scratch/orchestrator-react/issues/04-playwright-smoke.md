# 04: Playwright smoke 覆盖 + 截图对比

**What to build:** uitest smoke 套件新增 orchestrator 页用例:页面加载、发送消息、示例按钮、agents 面板。`python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm` 全绿。产出迁移前(Gradio)/后(React)截图对比,供用户过目(用户批准后 05 才可动)。

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] smoke 套件含 orchestrator 用例且通过
- [ ] 新旧页截图对比产出并给出路径
- [ ] 批次 1 报告落盘(docs/reports/)+ check_workflow.py 通过
