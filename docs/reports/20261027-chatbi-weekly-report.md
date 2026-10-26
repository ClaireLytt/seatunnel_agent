# 批次结果报告:经营周报 t2s-report(2026-10-27,收官批次)

## 批准依据

> 用户对第十六轮候选(建议"1(周报叙述)作为收官批次")回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中高 | `build_weekly_skeleton`:每指标 本周/上周总量(2 SQL/指标,上限 10)、周环比、月目标达成;告警中订阅清单(alert_state);最大变动 additive 指标的维度归因 Top3(best-effort);单指标失败只坏自己一行 | report.py(新) | 本批 |
| 中高 | `render_skeleton_md`(无 LLM 也可交付的表格版)+ `narrate`(LLM 摘要,系统提示硬性禁改/禁估/禁外推数字,失败返回 None 不碍落盘) | report.py | 本批 |
| — | CLI `t2s-report --ddl ... [--no-llm]`:落盘 `reports/t2s/weekly_<日期>.md` | cli_cmds/text2sql.py | 本批 |
| — | 指南"经营周报"节 | docs/chat_bi_guide.md | 本批 |

新增测试 1 条(多断言):demo 数据端到端骨架(周值/环比/目标/告警/归因全出)、Markdown 渲染断言、CLI --no-llm 真跑并校验落盘文件。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 174 source files
python -m pytest -q -k weekly -> 1 passed
python -m pytest -q          -> 3464 passed, 1 skipped, 243 deselected in 157.67s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3463 → 3464 passed(+1)。
- 行为:新增 `t2s-report` 命令;LLM 叙述路径未配置 key 时自动降级表格版。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | LLM 摘要的"禁改数字"靠提示词约束,无事后数字校验 | report.narrate | 校验要做数字抽取对账,收益待观察 | 极端情况下摘要可能出现骨架外数字 | 如发现实例,加"摘要中数字必须是骨架子串"的后校验 |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动;CLI 已真跑)。
- LLM 叙述路径:未用真实 key 执行(--no-llm 路径已端到端验证;narrate 失败降级有覆盖)。

## 功能线收官说明

至此 chat bi 功能线(2026-10-26/27,26 个批次)按计划画句号;剩余事项均为流程/产品决策:PR 合并(docs/PR_DRAFT_uiskill.md)、UI 露出(合并后)、三个重件(跨订阅聚合/NL 建指标/行级权限,需明确立项)。
