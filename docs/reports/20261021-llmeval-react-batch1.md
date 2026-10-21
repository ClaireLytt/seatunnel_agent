# 批次结果报告:LLM Eval React 迁移·批次 1(2026-10-21)

## 批准依据

> 用户在 grilling 轮确认 Q1–Q7 均 "yes"(含"沿用 Orchestrator 迁移全部共识"),随后以 `/implement-spec` 启动实施;分支要求原话:"就在现在的分支开发不允许切换新分支"(plat)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票01:validate(parse-only)/demo 薄端点 + 4 个 TestClient 测试 | agents/ai/llm_eval/api.py、tests/test_llm_eval.py | a42fa96 |
| 高 | 票02:frontend/llm_eval React workspace(编辑器/judge/运行/报告)、manifest external 切换 | frontend/llm_eval/、frontend/package.json、agents/ai/llm_eval/manifest.py | ebc69e8 |
| 高 | 票03:载入示例、校验、Recharts 趋势(TrendChart.tsx)、i18n 补齐 | frontend/llm_eval/src/ | 616bb15 |
| 高 | 票04:Playwright 页测 ×6、退役 yaml EVAL1–3、用例下限 37→34、前后截图 | tests/test_llmeval_page.py、ui_testing/cases/aiplatform.yaml、tests/test_ui_testing.py | 本报告同批提交 |

## 验证结果

```
ruff check src tests   -> All checks passed!
mypy                   -> Success: no issues found in 112 source files
pytest -q              -> 3267 passed, 1 skipped, 214 deselected
pytest -m uitest tests/test_llmeval_page.py -> 6 passed
npm run lint --workspace llm-eval-frontend  -> 通过(无输出)
npm run build --workspace llm-eval-frontend -> ✓ built in 7.50s(chunk >500 kB 警告,见遗留)
python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm
                       -> PASS 25 · FAIL 0 · ERROR 0(runs/20261021_004829/report.html)
python scripts/check_workflow.py -> 随本批次收尾执行,输出附对话
```

## 前后差异

- 测试类:llm_eval API 测试 46→50(+4 validate/demo);新增 6 个 Playwright 页测;uitest smoke 27→25 用例全绿(EVAL1/2 退役出 smoke,EVAL3 原属 full;等价覆盖移至 test_llmeval_page.py)。
- UI 类(docs/reports/shots/):
  - 旧 Gradio:llmeval-gradio-before-en-dark.png / -zh-light.png / -zh-validate.png
  - 新 React:llmeval-react-en-dark.png / -zh-light.png / -zh-validate.png(示例载入+校验通过+趋势面板)

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | llm_eval bundle 765 kB(recharts),构建 chunk >500 kB 警告 | npm build 输出 | 未做 code-split,uitest 同状 | 首屏体积偏大 | 后续统一对带图表页做 manualChunks |
| 低 | 趋势图需手动点"刷新趋势"才加载(与 Gradio 行为一致) | App.tsx trendRuns 初始 null | 1:1 平移 | 体验与旧页相同 | 如需自动加载另批改 |
| 低 | run 无进度流(同步请求) | spec 既定(Q5) | 保持后端零改动 | 大套件等待无进度 | 真不够用再立 SSE 票 |

## 未执行的步骤

- `seatunnel-agent ui --build` 全量构建人工过目:未执行(Playwright 已真浏览器覆盖;截图待用户过目)。
- 票05(退役 Gradio 旧页):未执行,等用户过目截图批准。
