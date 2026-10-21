# 02: Playwright 页测 + 截图对比 + 批次 1 报告

**What to build:** `tests/test_triage_page.py`(uitest 标记,先例 test_docqa_page.py):en 冒烟(控件/无 console error)、空 title 本地提示且不发 run 请求、无 key 时 503 detail 内联显示(确定性,屏蔽 .env/settings store,同 test_orchestrator_page.py 的三重 monkeypatch)、en-dark/zh-light 截图。无 yaml 退役,uitest 下限保持 29。before(Gradio)/after(React)截图;批次 1 报告 + check_workflow。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] 页测通过;uitest smoke 全绿;全量 ruff/mypy/pytest 通过
- [ ] before/after 截图入 docs/reports/shots/
- [ ] 批次 1 报告落盘(遗留清单含紫色 color #9333ea);check_workflow.py 通过
