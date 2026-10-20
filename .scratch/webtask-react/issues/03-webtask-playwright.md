# 03: Playwright 页测 + 截图对比 + 批次 1 报告

**What to build:** `tests/test_webtask_page.py`(uitest 标记,先例 test_codefix_page.py;不设 WEBTASK_API_ENABLED):en 冒烟、空 goal 本地提示且不发 run 请求、未设开关 403 内联显示(确定性,不起 Playwright 会话不调 LLM)、en-dark/zh-light 截图。无 yaml 退役,下限 29。before(Gradio)/after(React)截图;批次 1 报告(含 allow_private bug 修复记录)+ check_workflow。

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] 页测通过;uitest smoke 全绿;全量 ruff/mypy/pytest 通过
- [ ] before/after 截图入 docs/reports/shots/
- [ ] 批次 1 报告落盘;check_workflow.py 通过
