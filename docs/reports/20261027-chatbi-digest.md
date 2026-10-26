# 批次结果报告:chatbi 经营日报 digest(2026-10-27)

## 批准依据

> 用户对继续开发回复:"go on";本批取候选"定时经营摘要(digest)"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中高 | 新订阅类型 `digest`:每指标一行"昨日值/环比/月目标达成"的一张日报卡;≤2 SQL/指标、上限 10 指标;未定义/查询失败的指标只坏一行不坏整卡;空列表=全部已定义指标 | subscriptions.py | 本批 |
| — | CLI `t2s-sub add --digest "a,b,c"`(与 --metric/--watch/--freshness 互斥校验) | cli_cmds/text2sql.py | 本批 |
| — | 指南示例 | docs/chat_bi_guide.md | 本批 |

新增测试 2 条:日报卡端到端(GMV 环比 +10% / 月达成 2.1% / 比率与未定义指标行;outcome 结构化字段)+ store 校验(>10 指标拒绝、名单去空格)。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 107 source files
python -m pytest tests/test_text2sql_subscriptions.py -q -> 47 passed in 5.27s
python -m pytest -q          -> 3433 passed, 1 skipped, 243 deselected in 143.33s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3431 → 3433 passed(+2)。
- 行为:新增 digest 订阅类型(targets/watch/看板三件串成管理层一张卡);存量订阅不受影响。
- 非 UI 改动,uitest 未执行。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | digest 卡暂无异动标记(model 基线那套未接入,避免每指标再 +1 SQL) | _run_digest | 成本控制 | 日报不标注异常指标 | 需要时可加 `digest_watch=true` 选项按需开 |
| 低 | REST /subscriptions 仍不暴露 digest/watch 参数(既有边界) | api_subscriptions.py | 同前批 | 同前批 | 同前批 |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
