# 04: Playwright 页测 + 截图对比 + 批次 1 报告

**What to build:** `tests/test_llmcost_page.py`(uitest 标记,in-process uvicorn + dist,先例 test_promptlab_page.py;LLM_USAGE_PATH 指 examples/llmcost_demo/llm_usage_sample.jsonl,SEATUNNEL_PRICING_PATH 指 demo pricing.yaml):等价覆盖并退役 COST1(页面含"LLM 成本"无 Traceback)、COST2(价格表含 deepseek-chat/模型前缀)、COST3(切 7 天出现"近 7 天");另 en 冒烟、超预算横幅、en-dark/zh-light 截图。退役后用例下限 32→29。before(Gradio)/after(React)截图;批次 1 报告 + check_workflow。

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] 页测通过;COST1–3 退役且等价覆盖注明
- [ ] uitest smoke 全绿;全量 ruff/mypy/pytest 通过
- [ ] before/after 截图入 docs/reports/shots/
- [ ] 批次 1 报告落盘;check_workflow.py 通过
