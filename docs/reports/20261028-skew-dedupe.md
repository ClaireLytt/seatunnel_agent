# 批次结果报告:skew-dedupe(2026-10-28)

## 批准依据

> 用户:"go on"(对「skew 线 dedupe 质量收尾」提案的批准,走 /dedupe 技能;范围仅 agents/data/data_skew + cli_cmds/skew.py)。

## 扫描结论(4 组候选,收敛 2 组、放过 2 组)

| # | 重复内容 | 出现点 | 处置 |
| --- | --- | --- | --- |
| A | `compute_drift(t, splitkey_trend(t, n=50))` 式样 + n=50 魔数 | api/mcp/runtime/cli 共 7 处 | 收敛为 `drift.drift_for(history, table, column)`(TREND_DEPTH 常量化) |
| B | `-o` 落盘 + 「报告已保存」两行 | cli_cmds/skew.py 5 处 | 收敛为 `_save_report(path, text)` |
| C | webhook payload 组包(2 处) | skew.py | 放过:kind/字段语义不同,post_webhook 已共享,Rule of Three 不满足 |
| D | `splitkey_trend(n=8)` | skew-stats 展示 | 放过:展示深度,与评估深度用途不同(drift.py 注释已说明) |

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | A 组:`drift_for` + `TREND_DEPTH`,7 个调用点改写,孤儿 import 清理 | drift.py, api.py, mcp_server.py, runtime.py, cli_cmds/skew.py | 本批次 |
| 中 | B 组:`_save_report`,5 个调用点改写 | cli_cmds/skew.py | 本批次 |

无口径漂移(两组各处行为本就一致),无行为变化;临时改写脚本(.scratch 下本批自产)用后即删。

## 验证结果

```
ruff check src tests                 -> All checks passed!
mypy                                 -> Success: no issues found in 175 source files
pytest tests/test_data_skew.py -q    -> 215 passed in 9.99s
pytest -q(全量)                     -> 3520 passed, 1 skipped, 249 deselected, 2 warnings in 145.12s
python scripts/check_workflow.py     -> 提交后全 [PASS](见对话)
```

## 前后差异

- 测试数不变(行为不变是本批的正确结果);12 处重复调用点收敛到 2 个单一实现,n=50 魔数消失。

## 未解决问题 / 遗留清单

无(C、D 为有意放过,理由见上表)。

## 未执行的步骤

- uitest:无 UI 改动,不要求。
