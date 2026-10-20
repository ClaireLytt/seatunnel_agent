# 批次结果报告:LLM Cost React 迁移·批次 1(2026-10-21)

## 批准依据

> 用户在 grilling 轮确认 Q1–Q6 均 "yes"(含"沿用前三线全部共识"),随后以 `/implement-spec` 启动实施;分支要求原话:"就在现在的分支开发不允许切换新分支"(plat)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票01:prices 薄端点 + 3 个 TestClient 测试(含 override/malformed) | agents/ai/llm_cost/api.py、tests/test_llm_cost.py | 4286a09 + 1cf9851 |
| 高 | 票02:frontend/llm_cost React workspace(时间窗/预算/刷新/报告/横幅/no_data)、manifest external 切换 | frontend/llm_cost/、frontend/package.json、agents/ai/llm_cost/manifest.py | 2c0225b |
| 高 | 票03:成本/tokens 两张 Recharts 堆叠图(预算 ReferenceLine)、价格表折叠区、CSV 前端 Blob 导出、i18n | frontend/llm_cost/src/{Charts,PriceTable,csv}… | dc946cd |
| 高 | 票04:Playwright 页测 ×6、退役 yaml COST1–3、用例下限 32→29、前后截图 | tests/test_llmcost_page.py、ui_testing/cases/aiplatform.yaml、tests/test_ui_testing.py | 本报告同批提交 |

注:票01 首次提交时含 1 个失败测试(pytest 结果被管道截断掩盖,commit 后发现),随即以独立 fix commit 修正(override YAML 形状),`26 passed` 后才继续——如实记录。

## 验证结果

```
ruff check src tests   -> All checks passed!(exit 0)
mypy                   -> Success: no issues found in 112 source files
pytest -q              -> 3274 passed, 1 skipped, 221 deselected
pytest -m uitest tests/test_llmcost_page.py -> 6 passed
npm run lint --workspace llm-cost-frontend  -> 通过(无输出)
npm run build --workspace llm-cost-frontend -> ✓ built in 6.61s(chunk >500 kB 警告,recharts,同 llm_eval)
python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm
                       -> PASS 22 · FAIL 0 · ERROR 0(runs/20261021_020346/report.html)
python scripts/check_workflow.py -> 随本批次收尾执行,输出附对话
```

## 前后差异

- 测试类:llm_cost 测试 23→26(+3 prices);新增 6 个 Playwright 页测;uitest smoke 24→22 全绿(COST1/2 退役出 smoke,COST3 原属 full;等价覆盖移至 test_llmcost_page.py)。AI Platform 四页 React 页测合计 21 个(orchestrator 5 + llmeval 6 + promptlab 4 + llmcost 6)。
- UI 类(docs/reports/shots/):
  - 旧 Gradio:llmcost-gradio-before-en-dark.png / -zh-light.png / -zh-prices.png
  - 新 React:llmcost-react-en-dark.png / -zh-light.png / -zh-prices.png(报告+异常+两图+价格表)

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | react_migration.md "api= 留空"表述过时(prompt_lab 批次已记录) | hub/ui.py:199-206 | 文档滞后 | 新迁移者误导 | 票05 顺手更正(已写入票05) |
| 低 | recharts chunk >500 kB 构建警告(llm_eval 同状) | npm build 输出 | 未 code-split | 首屏体积 | 后续统一 manualChunks |
| 低 | budget 输入无防抖,击键即请求(对齐 Gradio budget.change) | App.tsx | 1:1 平移 | 本地只读聚合,开销小 | 保持现状 |

## 未执行的步骤

- `seatunnel-agent ui --build` 全量构建人工过目:未执行(Playwright 已真浏览器覆盖;截图待用户过目)。
- 票05(退役 Gradio 旧页 + 文档更正):未执行,等用户过目截图批准。
