# 批次结果报告:查询成本预估(2026-10-27)

## 批准依据

> 用户对第十四轮候选(建议"1(成本预估)")回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中高 | `scan_cost_hints`:分区表的事前扫描成本静态估算——单边界过滤(通过现有硬拦却无另一侧约束)、宽区间(含 BETWEEN,按日分区天数)、宽 IN 列表;精确分区/小区间/非日期形态静默 | partition.py | 本批 |
| 中高 | execute_sql 接入:`cost_hints` 附在结果里(与 review/skew 提示同风格,advisory 永不炸执行);`T2S_COST_WARN_PARTITIONS`(默认 90)调阈值;`T2S_COST_BLOCK_PARTITIONS=N` 可选硬拦(执行前拒绝) | tools_sql.py | 本批 |
| — | 指南"查询成本预估"节(护栏链:白名单→缺过滤硬拦→事前成本→事后倾斜) | docs/chat_bi_guide.md | 本批 |

新增测试 2 条(10 断言):单边界/宽区间 401 天(闰年含两端)/BETWEEN 等价/宽 IN=100/三种静默形态;硬拦环境变量三态(未设/达到/未达)。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 172 source files
python -m pytest tests/test_text2sql_metrics.py -q -> 97 passed in 11.30s
python -m pytest -q          -> 3462 passed, 1 skipped, 243 deselected in 158.25s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

调试记录:区间天数预期先写成 400,实测 401(2024 闰年、含两端)——按事实改断言。

## 前后差异

- 测试:3460 → 3462 passed(+2)。
- 行为:分区引擎 execute_sql 对宽扫描 SQL 多返回 `cost_hints`;设 BLOCK 阈值后超宽查询执行前被拒;sqlite 等非分区引擎零变化。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 估算假定日分区;月/小时分区的天数换算不准(只提示不拦,影响有限) | scan_cost_hints | 分区粒度元数据不可得 | 提示数字偏差 | 如需精确可读 SHOW PARTITIONS 实数(1 条额外查询) |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
