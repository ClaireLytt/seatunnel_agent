# 批次结果报告:floor-assert-update(2026-10-28)

## 批准依据

> 用户:"go on"(skew-drift-mcp 批次提交后 floor 误报,属验证闭环内的修复)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | floor [删断言] 放宽:同文件新增"仅数字不同"的同形断言视为更新预期,不再误报;真删除/换成弱断言仍命中 | scripts/check_workflow.py | 本批次 |
| 高 | floor 单测:数字更新不报、整删仍报、换弱断言仍报 | tests/test_check_workflow_floor.py | 本批次 |

## 验证结果

```
ruff check scripts tests                 -> All checks passed!
pytest tests/test_check_workflow_floor.py -q -> 18 passed in 0.69s
python scripts/check_workflow.py         -> 全 [PASS](含此前误报的 floor 项)
```

## 前后差异

- 测试类:test_check_workflow_floor.py 17 → 18 passed。
- 行为:skew-drift-mcp 批次中 `assert len(...) == 8 → == 9` 被 floor 误判为 [删断言];现该类"断言常数随代码增长更新"不再 FAIL。

说明:本批修改的是强制脚本本身,且动机是解除对我自己上一批提交的误报——已在对话中如实说明,放宽范围刻意收窄(仅数字归一化后完全同形才豁免)并补了反向用例。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- 全量 pytest:本批仅动 floor 检查与其单测,跑了定向 18 例;全量套件上一批次(15 分钟前)为 3497 passed。
