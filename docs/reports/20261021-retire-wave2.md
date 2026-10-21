# 批次结果报告:Gradio 退役·波 2(doc_qa/issue_triage/code_fix/web_task,2026-10-21)

## 批准依据

> 用户原话:"全部批准"(八个退役票;本波覆盖 docqa/triage 票 03 与 codefix/webtask 票 04,为最后一波)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 删除四个 Gradio 页(doc_qa 107 行、issue_triage 119、code_fix 164、web_task 160);UI-chrome i18n 随删,answer.py/report.py 后端渲染 key 保留 | agents/ai/{doc_qa,issue_triage,code_fix,web_task}/ui.py | 本报告同批提交 |
| 低 | 删除一次性截图脚本 shot_old.py ×4 与 hub_old.log(评审 C6 全量闭环) | .scratch/*/ | 同上 |

触点核对:`render_*`/模块 ui 引用全仓 grep 零命中;hub/css.py、ui_testing/page.py、catalog.py、tests 硬编码零残留;step_line 等 helper 无外部复用,随文件删除。

## 验证结果

```
ruff check src tests   -> All checks passed!(exit 0)
mypy                   -> Success: no issues found in 109 source files
pytest -q              -> 3286 passed, 1 skipped, 237 deselected
票级定向(6 文件)     -> 91 passed;四页测 -m uitest -> 16 passed
python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm
                       -> PASS 22 · FAIL 0(runs/20261021_095734/report.html)
python scripts/check_workflow.py -> 随本批次收尾执行,输出附对话
```

## 前后差异

- 代码:−696 行;mypy 源文件 113→109。两波合计:八个 Gradio 页 −1,878 行,全平台页面 100% React 化,仓库内不再有任何 `render_*_page` Gradio 入口。
- 行为:全量测试与 smoke 数字与退役前一致(3286 passed / PASS 22)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | hub 卡片紫色 color ×2(orchestrator #7c3aed、issue_triage #9333ea)违反禁蓝紫 | 两 manifest | 既有配置 | 卡片颜色 | 用户定夺新色后一并改 |
| 中 | text2sql src 6 个既有 lint 错误;test_sql_review_page stats 测试环境相关既有失败 | C2/C1 批次报告 | 既有问题 | lint 门禁/本机全量 uitest | 各另票 |
| 低 | 页测重写 shots/*.png 副产物(本波再现,已还原) | 两波备注 | 截图测试写仓库目录 | 工作区噪音 | 另票改输出到 runs/ |

## 未执行的步骤

无。
