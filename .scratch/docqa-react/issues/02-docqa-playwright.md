# 02: Playwright 页测 + 截图对比 + 批次 1 报告

**What to build:** `tests/test_docqa_page.py`(uitest 标记,in-process uvicorn + dist,先例 test_llmcost_page.py):en 冒烟(控件/无 console error)、extractive 提问(如 jdbc 相关)返回含来源的报告(确定性,不调 LLM)、空问题本地提示且不发 ask 请求、en-dark/zh-light 截图。无 yaml 用例退役,uitest 用例下限保持 29。before(Gradio)/after(React)截图;批次 1 报告 + check_workflow。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] 页测通过(pytest -m uitest tests/test_docqa_page.py)
- [ ] uitest smoke 全绿;全量 ruff/mypy/pytest 通过
- [ ] before/after 截图入 docs/reports/shots/
- [ ] 批次 1 报告落盘;check_workflow.py 通过
