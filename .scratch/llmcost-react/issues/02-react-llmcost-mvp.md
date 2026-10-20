# 02: React 页最小闭环 + manifest 切换

**What to build:** 打开 /llmcost 是 React 页:时间窗下拉(7/14/30/90 默认 30)、预算 Number 输入、刷新按钮;加载即拉 GET /summary(report:true)显示 Markdown 汇总;days/budget 变化即自动刷新;over_budget=true 显示超预算横幅(budget_over 文案),否则预算达标提示;空数据显示 no_data。manifest external=True, render="",api= 保留;workspace 目录名 = manifest.name "llm_cost",vite base '/llmcost/'。本票不做图表/价格表/CSV(票03)。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] frontend/llm_cost workspace 建立并入 workspaces(对标 frontend/prompt_lab 骨架)
- [ ] 控件/自动刷新/报告/横幅/no_data 可用
- [ ] manifest 切换完成,/llmcost 路由不变
- [ ] npm lint + build、ruff/mypy、定向 pytest(test_llm_cost/test_registry/test_hub_pages)通过
