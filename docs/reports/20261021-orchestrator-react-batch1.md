# 批次结果报告:Orchestrator React 迁移·批次 1(2026-10-21)

## 批准依据

> 用户在 grilling 轮逐项确认(Q1–Q9 均 "yes"),随后以 `/implement-spec` 指令启动实施;分支要求原话:"就在现在的分支开发不允许切换新分支"(当前分支 plat)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票01:SSE chat 端点(step/done/error 事件)、GET /session、POST /session/clear + 6 个 TestClient 测试 | src/seatunnel_agent/agents/ai/orchestrator/api.py、tests/test_orchestrator.py | 62362c2 |
| 高 | 票02:frontend/orchestrator React workspace(聊天流式/New session/无 LLM 降级/i18n)、manifest external=True 切换 | frontend/orchestrator/、frontend/package.json、agents/ai/orchestrator/manifest.py | e95679f |
| 高 | 票03:示例按钮×3、Routable agents 折叠面板、会话恢复、i18n 对齐 | frontend/orchestrator/src/{App.tsx,api.ts,i18n.ts} | 1449943 |
| 高 | 票04:Playwright 页测 ×5(含截图)、退役 yaml 用例 ORCH1、用例数下限 38→37 | tests/test_orchestrator_page.py、ui_testing/cases/aiplatform.yaml、tests/test_ui_testing.py | 本报告同批提交 |

## 验证结果

```
ruff check src tests   -> All checks passed!
mypy                   -> Success: no issues found in 112 source files
pytest -q              -> 3262 passed, 1 skipped, 210 deselected(修复用例下限后 tests/test_ui_testing.py -> 62 passed)
pytest -m uitest tests/test_orchestrator_page.py -> 5 passed
npm run lint --workspace orchestrator-frontend  -> 通过(无输出)
npm run build --workspace orchestrator-frontend -> ✓ built in 3.05s
python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm
                       -> PASS 27 · FAIL 0 · ERROR 0(runs/20261021_001628/report.html)
python scripts/check_workflow.py -> 见本报告提交(随批次收尾执行,输出附对话)
```

注:全量 pytest 首跑 1 failed(test_builtin_cases_load 用例数下限 38,ORCH1 退役后为 37),修正下限后该文件 62 passed;其余 3262 passed 不变。

## 前后差异

- 测试类:orchestrator 相关 37→43(unit,+6 SSE/session)再 +5 Playwright 页测;uitest smoke 27 用例全绿(ORCH1 退役,等价覆盖移至 test_orchestrator_page.py)。
- UI 类(截图 docs/reports/shots/):
  - 旧 Gradio:orchestrator-gradio-before-en-dark.png / -zh-light.png / -zh-agents.png
  - 新 React:orchestrator-react-en-dark.png / -zh-light.png / -zh-chat.png(含无 LLM 降级回复 + agents 面板)

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | manifest color 为紫色 #7c3aed,违反"禁蓝紫"UI 规范 | agents/ai/orchestrator/manifest.py | 既有 hub 卡片配置,非本次引入 | hub 卡片颜色 | 用户决定是否另批改色 |
| 低 | agents 目录说明列 en/zh 返回同一中文文案 | build_catalog(default_lang='en') 实测输出中文 | catalog 描述未做双语,旧页同样行为 | en 页面说明列为中文(与旧页一致) | 如需双语另立票改 catalog |
| 低 | 恢复的历史回复的 toolsUsed 小注不进入后续 history(Gradio 把 `<sub>` 注一并 seed) | frontend/orchestrator/src/App.tsx plainTurns | React 版实现更干净 | 对 LLM 上下文影响极小 | 保持现状 |
| 低 | 真实 LLM 的端到端聊天未在浏览器验证(仅无 LLM 降级路径) | test_orchestrator_page.py 用降级路径 | 测试不调真实 LLM(与仓库惯例一致) | 流式 step 渲染已由单测+SSE 契约覆盖 | 用户可手动起 ui 验证一次 |

## 未执行的步骤

- `seatunnel-agent ui --build` 全量构建起 hub 的人工页面验证:未执行(Playwright 页测已在真浏览器覆盖;等用户过目截图后如需我再起 hub)。
- 票05(退役 Gradio 旧页)未执行:按流程等用户过目截图批准后进行。
