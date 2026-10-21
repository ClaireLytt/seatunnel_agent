# 04: Playwright 页测 + 截图对比 + 批次 1 报告

**What to build:** `tests/test_promptlab_page.py`(uitest 标记,in-process uvicorn + dist,先例 test_llmeval_page.py):等价覆盖并退役 yaml 用例 PLAB1(空 prompt 点运行提示"请先输入 Prompt"且不发 /run 请求)、PLAB2(开历史折叠区点刷新,无 Traceback);另 en 冒烟(控件齐全/无 console error)、profiles 加载、en-dark/zh-light 截图。退役后 uitest 用例下限 34→32。before(Gradio)/after(React)截图;批次 1 报告落盘 + check_workflow。

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] 页测通过;PLAB1/2 退役且等价覆盖注明
- [ ] uitest smoke 全绿;全量 ruff/mypy/pytest 通过
- [ ] before/after 截图入 docs/reports/shots/
- [ ] 批次 1 报告落盘;check_workflow.py 通过
