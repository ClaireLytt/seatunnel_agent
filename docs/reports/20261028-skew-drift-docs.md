# 批次结果报告:skew-drift-docs(2026-10-28)

## 批准依据

> 用户:"go on"(drift 硬化批次后继续;本批为纯文档,补齐指南与新能力的差距)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | CLI 节新增 skew-drift 四种用法(单表/全表/--fail/--webhook) | docs/data_skew_guide.md | 本批次 |
| 中 | 漂移预警说明改为基线语义(中位数、≥3 次、三阈值、webhook drift_tables、仅漂移也告警) | docs/data_skew_guide.md | 本批次 |
| 中 | MCP 工具表加 skew_drift;UI 工作流加「倾斜漂移」卡片;判定阈值节加漂移阈值与按(表,键)隔离规则 | docs/data_skew_guide.md | 本批次 |

## 验证结果

```
ruff check src tests                 -> All checks passed!
pytest --collect-only -q             -> 3501/3749 tests collected (248 deselected)
python scripts/check_workflow.py     -> 提交后全 [PASS](见对话)
```

纯文档改动,按第 8 节仅要求以上两项;未跑全量 pytest/uitest。

## 前后差异

- 文档:docs/data_skew_guide.md 此前只有旧"较上次 +10pp"的单点漂移描述;现与实现一致(基线中位数、三指标阈值、四门面入口、CI 门禁与告警字段)。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- 全量 pytest / uitest:纯文档改动,第 8 节不要求。
