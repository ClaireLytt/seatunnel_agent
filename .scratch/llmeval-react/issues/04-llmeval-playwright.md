# 04: Playwright 页测 + 截图对比 + 批次 1 报告

**What to build:** `tests/test_llmeval_page.py`(uitest 标记,in-process uvicorn + dist,先例 test_orchestrator_page.py):等价覆盖并退役 yaml 用例 EVAL1(载入示例含 text2sql-golden)、EVAL2(坏套件报"期望顶层"无 Traceback)、EVAL3(空套件提示"请先粘贴"),加 en-dark/zh-light 截图。退役后 uitest 用例下限 37→34。产出 before(Gradio)/after(React)截图对比;批次 1 报告落盘。

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] 页测通过(pytest -m uitest tests/test_llmeval_page.py)
- [ ] EVAL1–3 从 aiplatform.yaml 退役,等价覆盖注明;uitest smoke 全绿
- [ ] before/after 截图入 docs/reports/shots/
- [ ] 全量 ruff/mypy/pytest + check_workflow.py;批次 1 报告落盘
