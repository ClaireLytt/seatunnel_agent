# 批次结果报告:Gradio 退役·波 1(AI Platform 四页,2026-10-21)

## 批准依据

> 用户原话:"全部批准"(针对八个退役票;本波覆盖 orchestrator/llm_eval/prompt_lab/llm_cost 的票 05)。经用户同意按两波执行、每波一份合并报告。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 删除四个 Gradio 页(orchestrator 312 行、llm_eval 218、llm_cost 272 含 matplotlib 两图+tempfile CSV、prompt_lab 233);UI-chrome i18n 随文件删,后端渲染 key(report.py/i18n.py)保留 | agents/ai/{orchestrator,llm_eval,prompt_lab,llm_cost}/ui.py | 本报告同批提交 |
| 中 | 更正 docs/react_migration.md 过时的 "api= 留空" 表述(hub 无条件挂载、保留 api= 为现行约定;promptlab/llmcost 批次遗留项闭环) | docs/react_migration.md:15-16 | 同上 |
| 低 | 删除一次性截图脚本 shot_old.py ×4 与 hub_old.log(评审报告 C6 部分闭环) | .scratch/*/ | 同上 |

触点核对:`ui:render_`/`from ...ui import` 全仓 grep 零命中;hub/css.py、ui_testing/page.py、catalog.py 零命中(此前票已清);manifest/test_registry 无需改;cjk_font_family 属 common/utils 他处仍用,无需搬移。

## 验证结果

```
ruff check src tests   -> All checks passed!(exit 0)
mypy                   -> Success: no issues found in 113 source files
pytest -q              -> 3286 passed, 1 skipped, 237 deselected
票级定向(7 个测试文件)-> 238 passed;四页测 -m uitest -> 21 passed
python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm
                       -> PASS 22 · FAIL 0(runs/20261021_094838/report.html)
python scripts/check_workflow.py -> 随本批次收尾执行,输出附对话
```

## 前后差异

- 代码:−1,182 行(四个 Gradio ui.py + 4 个 shot_old.py);mypy 源文件 114→113。
- 行为:四页 /orchestrator、/llmeval、/promptlab、/llmcost 仅剩 React 实现;全量测试数字与退役前一致(3286 passed)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | hub 卡片紫色 color(orchestrator #7c3aed、issue_triage #9333ea)仍违反禁蓝紫规范 | 两 manifest | 既有配置,此前批次遗留 | 卡片颜色 | 等用户定夺新色后一并改 |
| 低 | 页测运行会重写 docs/reports/shots/*.png(像素微差) | 本波再次出现,已 git restore | 截图测试副产物 | 工作区噪音 | 此前已记录,可另票改输出目录 |

## 未执行的步骤

- 退役波 2(doc_qa/issue_triage/code_fix/web_task):接续执行中。
