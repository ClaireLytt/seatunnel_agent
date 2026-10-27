# 批次结果报告:skew-splitkey-recovery(2026-10-28)

## 批准依据

> 用户:"go on"(对「批次 0:splitkey 路径补恢复卡」提案的批准;动手前按同意范围先将 origin/main 合并进 skew,merge 干净无冲突,9f17973)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | splitkey 巡检(单配置与目录两路径):已报漂移的表恢复稳定时,打印恢复卡、落 mode=drift/stable 记录、并入 webhook(复用 notify_decision 判定) | src/seatunnel_agent/cli_cmds/skew.py | 本批次 |
| 高 | 端到端测试:稳定实测 + 预置漂移记录 → 恢复卡出现在输出与 payload(drift_tables=["orders"]),历史落 stable 记录 | tests/test_data_skew.py | 本批次 |

## 验证结果

```
ruff check src tests                 -> All checks passed!
mypy                                 -> Success: no issues found in 175 source files
pytest tests/test_data_skew.py -q    -> 202 passed in 10.17s
pytest -q(全量)                     -> 见提交后对话(推送前实跑)
python scripts/check_workflow.py     -> 提交后全 [PASS](见对话)
```

无 UI 改动,未跑 uitest。

## 前后差异

- 测试类:test_data_skew.py 201 → 202 passed。
- 行为:经 splitkey 巡检发现的漂移,修复后同一巡检即发恢复卡,不再需要额外跑一次 skew-drift(上批遗留清零)。

## 未解决问题 / 遗留清单

无(原"splitkey 不发恢复卡"遗留项即本批)。

## 未执行的步骤

- uitest:无 UI 改动,不要求。
