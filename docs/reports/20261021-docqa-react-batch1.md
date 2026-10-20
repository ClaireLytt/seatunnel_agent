# 批次结果报告:Doc Q&A React 迁移·批次 1(2026-10-21)

## 批准依据

> 用户在 grilling 轮确认 Q1–Q5 均 "yes"(含三票精简链),随后以 `/implement-spec` 启动实施;分支要求原话:"就在现在的分支开发不允许切换新分支"(plat)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票01:frontend/doc_qa React workspace(问题输入/LLM 开关/Ask/Enter/报告区/空问题拦截/i18n)、manifest external 切换;零后端改动 | frontend/doc_qa/、frontend/package.json、agents/ai/doc_qa/manifest.py | 本批次首个 commit(git log "Doc Q&A React page") |
| 高 | 票02:Playwright 页测 ×4、前后截图;无 yaml 用例退役(uitest 下限保持 29) | tests/test_docqa_page.py | 本报告同批提交 |

## 验证结果

```
ruff check src tests   -> All checks passed!(exit 0)
mypy                   -> Success: no issues found in 112 source files
pytest -q              -> 3274 passed, 1 skipped, 225 deselected
pytest -m uitest tests/test_docqa_page.py -> 4 passed
npm run lint --workspace doc-qa-frontend  -> 通过(无输出)
npm run build --workspace doc-qa-frontend -> ✓ built in 2.86s
python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm
                       -> PASS 22 · FAIL 0 · ERROR 0(runs/20261021_022603/report.html)
python scripts/check_workflow.py -> 随本批次收尾执行,输出附对话
```

## 前后差异

- 测试类:新增 4 个 Playwright 页测(此页原本无 uitest yaml 覆盖,属净增);后端测试 48 passed 回归不变(零后端改动)。
- UI 类(docs/reports/shots/):
  - 旧 Gradio:docqa-gradio-before-en-dark.png / -zh-light.png / -zh-answer.png
  - 新 React:docqa-react-en-dark.png / -zh-light.png / -zh-answer.png(jdbc 提问的 extractive 答案+来源)

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | running 文案为自拟(旧页无运行中提示) | frontend/doc_qa/src/i18n.ts 注释 | 旧页一次性返回无提示 | 新增体验,非逐字平移 | 保持;措辞偏好可改 |
| 低 | LLM 作答路径未在真浏览器验证(仅 extractive) | test_docqa_page.py | 不调真实 LLM 的仓库惯例 | LLM 路径由 tests/test_doc_qa.py fake client 覆盖 | 保持 |

## 未执行的步骤

- `seatunnel-agent ui --build` 全量构建人工过目:未执行(Playwright 已真浏览器覆盖;截图待用户过目)。
- 票03(退役 Gradio 旧页):未执行,等用户过目截图批准。
