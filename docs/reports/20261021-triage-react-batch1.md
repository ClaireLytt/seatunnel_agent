# 批次结果报告:Issue Triage React 迁移·批次 1(2026-10-21)

## 批准依据

> 用户在 grilling 轮确认 Q1–Q5 均 "yes"(含 /run demo 默认值、保持同步与 repo_dir=None、三票链),随后以 `/implement-spec` 启动实施;分支要求原话:"就在现在的分支开发不允许切换新分支"(plat)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票01:/run issues 可空→默认加载 demo 历史(显式 [] 无历史)+2 测试;frontend/issue_triage React workspace(title/body/Triage/running/报告/空标题拦截/i18n);manifest external 切换 | agents/ai/issue_triage/{api.py,manifest.py}、frontend/issue_triage/、tests/test_issue_triage.py | 2890a16 |
| 高 | 票02:Playwright 页测 ×4(冒烟/空标题拦截/无 key 503 内联/截图)、前后截图;无 yaml 退役(下限 29) | tests/test_triage_page.py | 本报告同批提交 |

## 验证结果

```
ruff check src tests   -> All checks passed!(exit 0)
mypy                   -> Success: no issues found in 113 source files
pytest -q              -> 3280 passed, 1 skipped, 233 deselected
pytest -m uitest tests/test_triage_page.py -> 4 passed
npm run lint --workspace issue-triage-frontend  -> 通过(无输出)
npm run build --workspace issue-triage-frontend -> ✓ built in 3.48s
python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm
                       -> PASS 22 · FAIL 0 · ERROR 0(runs/20261021_031436/report.html)
python scripts/check_workflow.py -> 随本批次收尾执行,输出附对话
```

## 前后差异

- 测试类:issue_triage 测试 +2(demo 默认/空历史)再 +4 Playwright 页测(原无 uitest 覆盖,净增)。
- 行为差异:REST /run 省略 issues 时由"无历史"改为"demo 历史"(对齐旧页;显式 [] 保留旧 REST 语义)。
- UI 类(docs/reports/shots/):
  - 旧 Gradio:triage-gradio-before-en-dark.png / -zh-light.png / -zh-empty.png
  - 新 React:triage-react-en-dark.png / -zh-light.png / -zh-empty.png

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | manifest color #9333ea(紫)违反禁蓝紫规范 | agents/ai/issue_triage/manifest.py | 既有 hub 卡片配置 | hub 卡片颜色 | 与 orchestrator #7c3aed 一并由用户定夺 |
| 低 | 真实 LLM 分诊流未在浏览器端到端验证(503 路径代替) | test_triage_page.py | 不调真实 LLM 惯例 | 引擎/API 由 ScriptedClient 测试覆盖 | 保持 |
| 低 | running 文案自拟(旧页无) | frontend/issue_triage/src/i18n.ts 注释 | 旧页同步无提示 | 新增体验 | 保持 |

## 未执行的步骤

- `seatunnel-agent ui --build` 全量构建人工过目:未执行(Playwright 已真浏览器覆盖;截图待用户过目)。
- 票03(退役 Gradio 旧页):未执行,等用户过目截图批准。
