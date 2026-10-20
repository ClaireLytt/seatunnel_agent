# 批次结果报告:Prompt Lab React 迁移·批次 1(2026-10-21)

## 批准依据

> 用户在 grilling 轮确认 Q1–Q6 均 "yes"(含"沿用前两线全部共识"),随后以 `/implement-spec` 启动实施;分支要求原话:"就在现在的分支开发不允许切换新分支"(plat)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票01:diff(render_diff 复用)/history 薄端点 + 4 个 TestClient 测试 | agents/ai/prompt_lab/api.py、tests/test_prompt_lab.py | 5e62427 |
| 高 | 票02:frontend/prompt_lab React workspace(prompt/system/profiles/parallel/运行/报告)、manifest external 切换(api= 保留,核实见下) | frontend/prompt_lab/、frontend/package.json、agents/ai/prompt_lab/manifest.py | f07158a |
| 高 | 票03:Diff 折叠区、实验历史折叠区(加载预载+刷新)、i18n 补齐 | frontend/prompt_lab/src/ | d70373d |
| 高 | 票04:Playwright 页测 ×4、退役 yaml PLAB1/2、用例下限 34→32、前后截图 | tests/test_promptlab_page.py、ui_testing/cases/aiplatform.yaml、tests/test_ui_testing.py | 本报告同批提交 |

api= 核实:hub/ui.py:199-206 在 launch 后无条件挂载每个 manifest 的 api router(React 页后端依赖此路径),留空会导致默认模式下 /api/promptlab 不挂载;llm_eval/orchestrator 先例同样保留 api=。docs/react_migration.md 的"api= 留空"表述已过时(遗留清单)。

## 验证结果

```
ruff check src tests   -> All checks passed!
mypy                   -> Success: no issues found in 112 source files
pytest -q              -> 3271 passed, 1 skipped, 217 deselected
pytest -m uitest tests/test_promptlab_page.py -> 4 passed
npm run lint --workspace prompt-lab-frontend  -> 通过(无输出)
npm run build --workspace prompt-lab-frontend -> ✓ built in 3.01s
python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm
                       -> PASS 24 · FAIL 0 · ERROR 0(runs/20261021_012440/report.html)
python scripts/check_workflow.py -> 随本批次收尾执行,输出附对话
```

## 前后差异

- 测试类:prompt_lab API 测试 19→23(+4 diff/history);新增 4 个 Playwright 页测;uitest smoke 25→24 用例全绿(PLAB1 退役出 smoke,PLAB2 原属 full;等价覆盖移至 test_promptlab_page.py)。
- UI 类(docs/reports/shots/):
  - 旧 Gradio:promptlab-gradio-before-en-dark.png / -zh-light.png / -zh-empty.png
  - 新 React:promptlab-react-en-dark.png / -zh-light.png / -zh-empty.png(空 prompt 提示 + Diff/历史面板)

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | docs/react_migration.md "api= 留空"表述与 hub/ui.py:199-206 现行逻辑矛盾 | 票02 核实(本报告上文) | 文档滞后于挂载逻辑改动 | 新迁移者照文档留空会导致后端不挂载 | 票05 退役批顺手更正文档 |
| 低 | React 版 running 文案为自拟(Gradio 版无该键) | frontend/prompt_lab/src/i18n.ts 注释 | 旧页运行中无提示,React 需要 | 文案非逐字平移(新增体验) | 保持;如有措辞偏好告知即改 |
| 低 | 历史表头拆为独立 i18n 键(文案一致) | 票03 汇报 | 结构差异 | 无 | 保持现状 |

## 未执行的步骤

- `seatunnel-agent ui --build` 全量构建人工过目:未执行(Playwright 已真浏览器覆盖;截图待用户过目)。
- 票05(退役 Gradio 旧页):未执行,等用户过目截图批准。
