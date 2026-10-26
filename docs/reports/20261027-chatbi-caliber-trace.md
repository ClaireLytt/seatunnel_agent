# 批次结果报告:chatbi 口径变更追溯(2026-10-27)

## 批准依据

> 用户对继续开发回复:"go on";本批取候选"口径变更可追溯"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | `diff_metric_stores`:两份指标库的口径级 diff(CALIBER_FIELDS:expression/filters/joins/targets 等;display_name 之类展示字段不算变更) | metrics.py | 本批 |
| 中 | `metrics validate` 通过后自动对比 git HEAD 版 metrics.yaml,打印 新增/删除/字段级变化,并点名受影响订阅(含 digest 的 metrics 列表);无 git/未跟踪时静默跳过 | cli_cmds/text2sql.py | 本批 |
| — | 指南说明 | docs/chat_bi_guide.md | 本批 |

新增测试 2 条:diff 纯函数(增/删/expression 变更字段级输出)+ 展示字段变更保持静默。CLI 在临时真 git 仓库里 smoke 验证(输出贴下节),探针脚本已清理。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 107 source files
python -m pytest tests/test_text2sql_metrics.py -q -> 86 passed in 9.03s
python -m pytest -q          -> 3435 passed, 1 skipped, 243 deselected in 139.66s
CLI smoke(临时 git 仓库,改 expression 后 validate):
  校验通过：1 个指标定义与 DDL 一致
  口径相对上一提交发生变化:
    ~ gmv.expression: 'SUM(x)' → 'SUM(pay_amount)'
  rc: 0
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3433 → 3435 passed(+2)。
- 行为:`metrics validate` 退出码语义不变(CI 门禁兼容),通过后多打印口径 diff 与受影响订阅;无变化/无 git 时输出与之前完全一致。
- 非 UI 改动,uitest 未执行。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 口径变更只在 CLI validate 时可见,未落 qlog 审计事件 | _report_caliber_changes | 范围控制 | 变更历史靠 git log 追 | 需要时在 diff 非空时写一条 qlog kind=caliber_change |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
