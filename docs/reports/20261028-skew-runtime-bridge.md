# 批次结果报告:skew-runtime-bridge(2026-10-28)

## 批准依据

> 用户:"go on"(对「运行时 → 分片键闭环指引」提案的批准;动手前已按同意范围同步 origin/main 进 skew,cfbf7b0,无冲突)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `implicated_tables(stages)`:从拖尾 vertex 名(`Source:/Sink: X`)与 Spark `sql_desc`(`insert ... table X` / `from X`)确定被牵连表,确定性正则,解析不出不猜 | agents/data/data_skew/runtime.py | 本批次 |
| 高 | `diagnose_and_log` 尾部(四入口自动获得):被牵连表**有巡检历史 → 内联 drift 判定**;无历史 → `rt_table_next` 指引跑 skew-splitkey;全 ok 不加尾巴;最多 3 表 | agents/data/data_skew/runtime.py | 本批次 |
| 中 | rt_table_next i18n(zh/en) | agents/data/data_skew/i18n.py | 本批次 |
| 高 | 测试:表名提取(Flink 名/Spark SQL/ok 跳过/不可解析跳过/去重)、尾行两分支、全 ok 无尾巴 | tests/test_data_skew.py | 本批次 |

## 验证结果

```
ruff check src tests                 -> All checks passed!
mypy                                 -> Success: no issues found in 175 source files
pytest tests/test_data_skew.py -q    -> 208 passed in 10.46s
pytest -q(全量)                     -> 3512 passed, 1 skipped, 249 deselected, 2 warnings in 144.82s
python scripts/check_workflow.py     -> 提交后全 [PASS](见对话)
```

无 UI 代码改动(REST/页面经 report 文本自动获得),未跑 uitest。

## 前后差异

- 测试类:test_data_skew.py 206 → 208;全量 3510 → 3512 passed。
- 行为:运行时报告此前止于 AQE 参数与"粘到静态分析"的泛泛建议;现在拖尾 stage 指到表时,直接给出该表的漂移判定(有历史)或精确的下一步命令(无历史)——issue #21 两条线闭环。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- uitest:无 UI 改动,不要求。
