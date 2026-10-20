# 批次结果报告:Code Fix React 迁移·批次 1(2026-10-21)

## 批准依据

> 用户在 grilling 轮确认 Q1–Q5 均 "yes"——特别是 Q3 安全决策:"迁,但带强制白名单(默认拒绝)";随后以 `/implement-spec` 启动实施;分支要求原话:"就在现在的分支开发不允许切换新分支"(plat)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票01:SSE run 端点(step→done/error)+ 强制白名单 CODEFIX_API_ALLOWED_DIRS(未配置/越界一律 403)+ 4 个 TestClient 测试;manifest 挂 api(原 api=None 刻意无 REST,经用户 Q3 确认以默认拒绝换迁移);HTTP 面不暴露 in_place | agents/ai/code_fix/{api.py,manifest.py}、tests/test_code_fix.py | f7f642e |
| 高 | 票02:frontend/code_fix React workspace(path/tests/instruction/步数 Slider/流式步骤/结构化终态报告)、manifest external 切换 | frontend/code_fix/、frontend/package.json、agents/ai/code_fix/manifest.py | a435387 |
| 高 | 票03:Playwright 页测 ×4(冒烟/空 path 拦截/403 内联显示/截图)、前后截图;无 yaml 用例退役(uitest 下限保持 29) | tests/test_codefix_page.py | 本报告同批提交 |

## 验证结果

```
ruff check src tests   -> All checks passed!(exit 0)
mypy                   -> Success: no issues found in 113 source files
pytest -q              -> 3278 passed, 1 skipped, 229 deselected
pytest -m uitest tests/test_codefix_page.py -> 4 passed
npm run lint --workspace code-fix-frontend  -> 通过(无输出)
npm run build --workspace code-fix-frontend -> ✓ built in 3.07s
python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm
                       -> PASS 22 · FAIL 0 · ERROR 0(runs/20261021_025342/report.html)
python scripts/check_workflow.py -> 随本批次收尾执行,输出附对话
```

## 前后差异

- 测试类:code_fix 测试 9→13(+4 API:403×2/SSE 序列/无 key 降级);新增 4 个 Playwright 页测(原无 uitest 覆盖,净增)。
- 安全面:原"无 REST"→"有 REST 但默认 403"(未配置 CODEFIX_API_ALLOWED_DIRS 时行为等同无 REST;页测截图即 403 路径)。
- UI 类(docs/reports/shots/):
  - 旧 Gradio:codefix-gradio-before-en-dark.png / -zh-light.png / -zh-empty.png
  - 新 React:codefix-react-en-dark.png / -zh-light.png / -zh-403.png(白名单未配置的内联拒绝)

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | 真实修复流(白名单内+真 LLM)未在浏览器端到端验证 | 页测仅覆盖 403/拦截路径 | ScriptedClient 无法注入 HTTP 进程、不调真实 LLM 惯例 | SSE 契约已由 TestClient 假 LLM 全覆盖 | 用户可本机配白名单人工跑一次;或后续加注入缝 |
| 低 | 前端 i18n 的 noKey 键平移后未引用(无 key 由后端 error 事件带文案) | frontend/code_fix/src/i18n.ts | 实现差异 | 无 | 票04 退役时顺手删或保留 |
| 低 | 终态版式较 report.py 多"最终测试输出"小标题 | App.tsx | 结构化版式需命名代码块 | 文案增量 | 保留 |

## 未执行的步骤

- `seatunnel-agent ui --build` 全量构建人工过目:未执行(Playwright 已真浏览器覆盖;截图待用户过目)。
- 票04(退役 Gradio 旧页):未执行,等用户过目截图批准。
