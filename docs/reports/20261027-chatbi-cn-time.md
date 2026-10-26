# 批次结果报告:中文业务时间语义(2026-10-27)

## 批准依据

> 用户对第十三轮候选(建议"1(中文时间语义)")回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | calendar_cn 重构为命名区间单源:`HOLIDAY_RANGES[year][name]`(HOLIDAYS 从其派生,官方天数既有测试守住);`named_holiday_range` 支持别名(五一/十一/过年…)、`期间/假期` 后缀、显式年份,无年份取今天之前最近一次,未覆盖年份返回 None 不猜 | calendar_cn.py | 本批 |
| 高 | `resolve_named_range`:相对期(今天/昨天/本周/上周/本月/上月/本季度/上季度/今年/去年/近N天)+ 节假日;`parse_time_range` 单 start 输入先试命名解析——指标查询/归因/指标树/REST/MCP 全部入口自动受益 | metrics.py | 本批 |
| — | 提示词第 14 条:命名时间原样透传,禁止 LLM 自算日期 | prompts.py | 本批 |
| — | 指南"中文业务时间语义"节 | docs/chat_bi_guide.md | 本批 |

新增测试 2 条(18 断言):相对期全覆盖(周一边界/季度边界/近N天)、节假日(最近一次/别名/后缀/显式年/未覆盖年/未知词 None)、parse_time_range 命名路径与普通日期路径互不影响。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 172 source files
python -m pytest tests/test_text2sql_metrics.py -q -> 95 passed in 10.81s
python -m pytest -q          -> 3460 passed, 1 skipped, 243 deselected in 152.89s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

节假日官方天数回归(test_calendar_cn_official_counts)在重构后首跑即过——HOLIDAYS 派生式与原手写集合逐日一致。

## 前后差异

- 测试:3458 → 3460 passed(+2,18 断言)。
- 行为:"春节期间的 GMV" 从"LLM 猜日期"变为"官方区间确定性解析";普通日期入参路径逐字节不变。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 2027 年节假日未发布(国务院通常 11 月发文),届时需人工补 HOLIDAY_RANGES | calendar_cn.py 注释 | 外部事实 | 2027 的命名查询返回 None(显式不猜) | 发文后一次 10 行数据补录 |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
