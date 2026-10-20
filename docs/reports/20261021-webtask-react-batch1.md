# 批次结果报告:Web Task React 迁移·批次 1(2026-10-21)

## 批准依据

> 用户在 grilling 轮确认 Q1–Q5 均 "yes"——特别是 Q3 安全决策("默认关闭:WEBTASK_API_ENABLED 未设一律 403")与 Q4 既有 bug 处置(b 方案:allow_private 透传、仅环回放行);随后以 `/implement-spec` 启动实施;分支要求原话:"就在现在的分支开发不允许切换新分支"(plat)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票01:SSE run 端点(step→done/error)+ WEBTASK_API_ENABLED 门(未设=403)+ **allow_private 透传修复既有 bug**(旧页默认 127.0.0.1 必败;仅环回放行,私网仍拒;HTTP 不暴露 allow_external/headed)+ 6 个测试 | agents/ai/web_task/{api.py,engine.py,manifest.py}、tests/test_web_task.py | fe0d02e |
| 高 | 票02:frontend/web_task React workspace(goal/url/步数 Slider/流式步骤/终态报告)、manifest external 切换 | frontend/web_task/、frontend/package.json、agents/ai/web_task/manifest.py | 255b1b9 |
| 高 | 票03:Playwright 页测 ×4(冒烟/空 goal 拦截/403 内联/截图)、前后截图;无 yaml 退役(下限 29) | tests/test_webtask_page.py | 本报告同批提交 |

## 验证结果

```
ruff check src tests   -> All checks passed!(exit 0)
mypy                   -> Success: no issues found in 114 source files
pytest -q              -> 3286 passed, 1 skipped, 237 deselected
pytest -m uitest tests/test_webtask_page.py -> 4 passed
npm run lint --workspace web-task-frontend  -> 通过(无输出)
npm run build --workspace web-task-frontend -> ✓ built in 2.94s
python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm
                       -> PASS 22 · FAIL 0 · ERROR 0(runs/20261021_064602/report.html)
python scripts/check_workflow.py -> 随本批次收尾执行,输出附对话
```

## 前后差异

- 测试类:web_task 测试 12→18(+2 引擎透传 +4 API);新增 4 个 Playwright 页测(原无 uitest 覆盖,净增)。
- 行为差异:① REST 面从无到"默认 403 的 SSE 端点";② 既有 bug 修复——UI/API 用默认环回 URL 不再被 SSRF 守卫误拒(非环回私网仍拒)。
- UI 类(docs/reports/shots/):
  - 旧 Gradio:webtask-gradio-before-en-dark.png / -zh-light.png / -zh-empty.png
  - 新 React:webtask-react-en-dark.png / -zh-light.png / -zh-403.png(默认关闭门的内联拒绝)

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | 真实浏览器任务流(开关开启+真 LLM+Playwright 会话)未端到端验证 | 页测仅 403/拦截路径 | 不调真实 LLM、页测进程不起二级浏览器 | SSE 契约与环回放行由 TestClient 离线夹具覆盖 | 用户可本机设 WEBTASK_API_ENABLED=1 人工跑一次 |
| 低 | stepLine 文案去掉了 {inp} 槽(SSE step 事件不含 input) | frontend/web_task/src/i18n.ts 注释 | 事件契约最小化 | 步骤行少显示入参摘要 | 如需要可在 step 事件加 input 预览,另批 |
| 低 | 终态 ✅/❌ 文案自拟(旧页由后端 render 输出) | i18n.ts 注释 | 前端结构化版式 | 文案非逐字 | 保持 |

## 未执行的步骤

- `seatunnel-agent ui --build` 全量构建人工过目:未执行(Playwright 已真浏览器覆盖;截图待用户过目)。
- 票04(退役 Gradio 旧页):未执行,等用户过目截图批准。
