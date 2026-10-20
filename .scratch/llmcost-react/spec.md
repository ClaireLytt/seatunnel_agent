# LLM Cost React Migration

Labels: `ready-for-agent`
Branch: `plat`(用户要求:直接在 plat 开发提交,不切新分支)

## Problem Statement

LLM Cost 页面(/llmcost)是 AI Platform 工作区最后一个 Gradio 页,与已迁 React 的页面(含本轮 orchestrator/llm_eval/prompt_lab)视觉与技术栈不一致;matplotlib 静态图无交互,维护两套 UI 栈成本高。

## Solution

按既有迁移先例把 LLM Cost 1:1 迁为独立 React workspace:时间窗/预算控件、刷新、成本汇总 Markdown 报告 + 超预算横幅、按日堆叠成本图(含日均预算参考线)与按模型 tokens 堆叠图(Recharts)、价格表折叠区、CSV 导出(前端生成)。复用 @shared 与 engineering-paper 主题;验证通过后退役 Gradio 旧页(含 matplotlib 图代码)。不加新功能。

## User Stories

1. As a platform operator, I want the LLM Cost page rendered in React with the shared visual language, so that the AI Platform workspace is fully coherent
2. As a cost watcher, I want a time-window selector (7/14/30/90 days, default 30), so that I control the analysis span
3. As a cost watcher, I want an optional daily-budget input, so that overspend is flagged
4. As a cost watcher, I want a refresh action (and auto-refresh on control change), so that the view follows my inputs
5. As a cost watcher, I want the cost summary as a Markdown report (totals, by model, by agent, anomalies, unpriced warnings), so that I see spend at a glance
6. As a cost watcher, I want an over-budget banner when spend exceeds budget, so that overruns are obvious
7. As a cost watcher, I want a stacked per-day cost chart with a dashed daily-budget reference line, so that I spot expensive days
8. As a cost watcher, I want a per-model input/output tokens stacked chart, so that I see which model consumes most
9. As a cost watcher, I want a "no data" notice when the usage log is empty, so that an empty chart isn't confusing
10. As a cost watcher, I want a collapsible price table (prefix/input/output/source) with the override-file note, so that I can audit pricing
11. As a cost watcher, I want a CSV export of the summary, so that I can analyze spend elsewhere
12. As a Chinese-speaking user, I want en/zh copy to follow the st-lang cookie, so that language stays consistent
13. As a platform user, I want dark/light theme to follow the shared theme, so that the page matches the hub
14. As a platform operator, I want the page mounted via the manifest external-app convention, so that ui --build serves it like every workspace
15. As a developer, I want API + Playwright coverage for the migrated page, so that regressions are caught
16. As a developer, I want the Gradio page (and its matplotlib figures) removed after cutover, so that only one implementation remains

## Implementation Decisions

- 新建独立 workspace `frontend/llm_cost`(目录名 = manifest.name,route 仍 /llmcost,vite base '/llmcost/');仪表盘形态参照 data_comparison 先例(react_migration.md 推荐),图表样式沿 uitest CountsChart/llm_eval TrendChart 先例
- 复用 @shared(card/theme/lang/ReportView);Recharts:成本图 = by_day 堆叠(按 model 分色,数据自 summary.by_day_model)+ ReferenceLine(budget);tokens 图 = by_model input/output 堆叠
- 后端仅加一个薄端点:prices(merged_prices 列表 {prefix,input_usd,output_usd,source} + override 路径信息);summary/health 不动;aggregate/pricing/report 引擎零改动
- CSV 导出由前端从 summary JSON 生成 Blob 下载(UTF-8 BOM,列结构对齐旧页 _csv_file),不加后端端点
- 刷新语义对齐旧页:days/budget 变化即刷新 + 手动刷新按钮;加载时自动拉取(30 天默认)
- manifest 切 external=True, render="";api= 保留(hub 启动后无条件挂载,先例已核实)
- i18n:UI 字典(title/days_label/budget_label/refresh_btn/price_acc/price_note/chart_cost/chart_tokens/budget_line/budget_ok/budget_over/csv_btn/no_data)平移 i18next;后端 i18n 的 rpt_* 键保留 Python 侧
- 退役阶段:删 Gradio ui 模块(含 matplotlib _cost_figure/_tokens_figure/_csv_file)及触点(aiplatform.yaml COST1–3、catalog.py、test_registry.py 等);同批顺手更正 react_migration.md 已过时的 "api= 留空" 表述(prompt_lab 批次遗留)
- 两批:批次 1 = T1 /prices → T2 React MVP+manifest → T3 两图/价格表/CSV/i18n → T4 页测+截图+报告;批次 2(用户过目批准)= T5 退役
- UI 约束:禁蓝紫及渐变;图表用主题 token 配色;manifest color #f59e0b(琥珀)合规不动

## Testing Decisions

- 只测外部行为;前端组件不做单测
- 缝 1(REST API):pytest TestClient 覆盖 prices(内置价目含 deepseek-chat、override 生效、malformed 400 或错误传达)、summary 回归;先例 tests/test_llm_cost.py TestApi
- 缝 2(真浏览器):`tests/test_llmcost_page.py`(uitest 标记,in-process uvicorn + dist,先例 test_promptlab_page.py),LLM_USAGE_PATH 指向 examples/llmcost_demo 样例数据;等价覆盖退役的 COST1(页面含"LLM 成本"无 Traceback)、COST2(价格表含 deepseek-chat/模型前缀)、COST3(切 7 天出现"近 7 天");另:预算超支横幅、en/zh 截图(before/after)
- 退役 COST1–3 后 uitest 用例下限 32→29
- 验证命令:ruff/mypy/pytest、npm lint/build(llm_cost workspace)、uitest smoke --no-llm、check_workflow.py
- 不调真实 LLM;数据全部来自 demo JSONL(确定性)

## Out of Scope

- aggregate/pricing/report 引擎改动或新功能;后端 CSV 端点
- 其他页面迁移;main 操作、新分支、PR;前端组件单测

## Further Notes

- 探查依据:manifest(render=ui:render_llm_cost_page,无 external)、api.py 仅 summary/health、ui.py 区块/回调/matplotlib 图、uitest COST1–3、tests/test_llm_cost.py、LLM_USAGE_PATH/SEATUNNEL_PRICING_PATH env、examples/llmcost_demo
- 用户已在 grilling(Q1–Q6)确认全部决策
