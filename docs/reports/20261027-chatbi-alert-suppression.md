# 批次结果报告:chatbi 告警抑制与恢复通知(2026-10-27)

## 批准依据

> 用户对第三轮候选清单(建议"1(告警抑制聚合)单独一批")回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 告警记忆:watch 订阅持续同向异常只推首日一张卡(后续 `suppressed` 静默并保留首日 since);恢复正常推一张绿色"已恢复"卡(`recovered`,含告警起始日);方向反转视为新事件重新告警 | subscriptions.py `_run_metric_watch` | 本批 |
| 高 | 状态持久化:`SubscriptionStore.record_alert_state`;Scheduler 与 CLI `t2s-sub run` 在 outcome 带 alert_state 时落盘 | subscriptions.py, cli_cmds/text2sql.py | 本批 |
| — | 指南说明 | docs/chat_bi_guide.md | 本批 |

新增测试 3 条:三日事故两张卡(告警→抑制→恢复绿卡,断言 since 保留与卡片文案)/ 方向反转重新告警 / 状态落盘重读。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 107 source files
python -m pytest tests/test_text2sql_subscriptions.py -q -> 50 passed in 7.94s
python -m pytest -q          -> 3438 passed, 1 skipped, 243 deselected in 151.70s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3435 → 3438 passed(+3)。
- 行为:同一异常持续 N 天,从 N 张重复卡变为 1 张告警卡 + 1 张恢复卡;无状态的存量订阅首次运行行为与之前一致(首日照常告警)。
- 非 UI 改动,uitest 未执行。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | 跨订阅告警聚合(一天多指标告警合并一张卡)未做 | 本批范围说明 | 需要把"引擎内直接推送"重构为"推送延迟到调度层合并",影响面大 | 告警风暴日仍一订阅一张卡 | 单独批次:run_subscription 增加 defer_push 模式,Scheduler 按 webhook 分组合并 |
| 低 | no_data 日不改变告警状态(保守选择):断更期间事故恢复的绿卡会迟到 | _run_metric_watch | 断更日无法判断是否恢复 | 恢复通知延后到数据恢复日 | 符合预期,文档化即可 |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
