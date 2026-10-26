# 批次结果报告:跨订阅告警聚合(2026-10-27)

## 批准依据

> 用户在"剩余可做项只有重件"的说明后回复:"go on",取重件中规格最明确的跨订阅聚合(此前批次遗留,曾注明"需推送延迟重构,单独批次")。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中高 | `notify.aggregate_pushes()` 线程局部上下文:上下文内 `push_card` 的红卡(ok=False)按 webhook 缓冲并返回 deferred;绿卡直发;`flush_aggregated` 冲刷——单卡原样、多卡合并为"⚠️ N 条告警"(分节 markdown) | notify.py | 本批 |
| 中高 | `Scheduler.check_once` 整轮包裹聚合上下文(循环抽为 `_run_due`),轮末冲刷;`T2S_ALERT_AGGREGATE=0` 关闭;CLI run-now/REST 无上下文不受影响;record_run 状态不变(deferred 视为推送成功) | subscriptions.py | 本批 |
| — | 指南说明 | docs/chat_bi_guide.md | 本批 |

新增测试 2 条:聚合上下文单元(缓冲/绿卡直发/多卡合一含分节/单卡原样/上下文外直发)、调度器端到端(同轮两 watch 同 webhook → 恰一张"⚠️ 2 条告警"、两订阅状态各自 alerted)。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 174 source files
python -m pytest tests/test_text2sql_subscriptions.py -q -> 60 passed in 6.62s
python -m pytest -q          -> 3472 passed, 1 skipped, 246 deselected in 170.69s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3470 → 3472 passed(+2)。
- 行为:告警风暴日(一轮多个订阅同时告警)从"每订阅一张红卡刷屏"变为"每渠道一张聚合卡";单告警/绿卡/手动 run 逐字节不变。

## 未解决问题 / 遗留清单

无。重件清单剩:NL 建指标、行级权限(均需明确立项)。

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
