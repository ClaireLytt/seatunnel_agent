# 批次结果报告:skew-drift-hardening(2026-10-28)

## 批准依据

> 用户:"go on"(对「drift 巡检硬化:skew-drift --fail + splitkey webhook 并入 drift」提案的批准)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `skew-drift --fail`:存在漂移判定时 exit 1(CI 门禁,沿用 splitkey 门禁文案风格) | src/seatunnel_agent/cli_cmds/skew.py | 本批次 |
| 高 | `skew-splitkey` webhook 并入 drift:单配置与目录两路径,漂移表进 `drift_tables` 字段、漂移行追加进 text;仅 drift(无 bad/errors)也触发;无漂移时 payload 与此前完全一致 | src/seatunnel_agent/cli_cmds/skew.py | 本批次 |
| 高 | 测试:--fail 漂移退出 1 / 无 --fail 仍 0 / 稳定时 --fail 为 0;目录巡检 payload 含 drift_tables 与漂移文本;无漂移 payload 无该字段 | tests/test_data_skew.py | 本批次 |

## 验证结果

```
ruff check src tests                 -> All checks passed!
mypy                                 -> Success: no issues found in 175 source files
pytest tests/test_data_skew.py -q    -> 196 passed in 7.20s
pytest -q(全量)                     -> 3500 passed, 1 skipped, 248 deselected, 2 warnings in 147.03s
python scripts/check_workflow.py     -> 提交后全 [PASS](见对话)
```

无 UI 改动,未跑 uitest。

## 前后差异

- 测试类:test_data_skew.py 193 → 196;全量 3497 → 3500 passed。
- 行为:漂移此前只能看(advisory);现在可卡 CI(`--fail`),且 splitkey 巡检在键"尚未坏但正在恶化"时也会进群告警(此前 webhook 仅 bad/errors 触发)。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- uitest:无 UI 改动,不要求。
