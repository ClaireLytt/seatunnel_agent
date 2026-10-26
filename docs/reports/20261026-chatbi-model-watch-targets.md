# 批次结果报告:chatbi 模型基线异动 + 目标达成跟踪(2026-10-26)

## 批准依据

> 用户对新功能候选清单(推荐"1+2 为一组")回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 异动监控 `watch_mode=model`:预测基线(趋势+星期+节假日)95% 区间外才告警,替代固定阈值;历史不足/区间未覆盖记 no_data;卡片展示 实际 vs 预期[lo,hi] | subscriptions.py, cli_cmds/text2sql.py | 本批 |
| 高 | 目标达成跟踪:`metrics.yaml targets: {month/quarter/year}`(additive 专属,解析校验);新工具 `metric_target_progress` 期初至今实际÷目标 + 期末投影(forecast 优先,历史<7 天退化 linear_pace);qlog kind=target | metrics.py, tools_metric.py, tools.py, prompts.py | 本批 |
| — | 指南:targets 字段、目标达成跟踪章节、model watch 示例 | docs/chat_bi_guide.md | 本批 |

新增测试 9 条:model watch 告警/静默/历史不足(真 sqlite 端到端)、targets 解析/四类校验错误、target 工具端到端(数字恒等校验 6090/6975)/linear_pace 退化/未声明目标。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 107 source files
python -m pytest tests/test_text2sql_metrics.py tests/test_text2sql_forecast.py tests/test_text2sql_subscriptions.py -q -> 151 passed in 11.67s
python -m pytest -q          -> 3418 passed, 1 skipped, 243 deselected in 140.34s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3409 → 3418 passed(+9)。
- 行为:`--watch-mode model` 新增(dod/wow 行为不变);`metrics.yaml` 新增可选 `targets`(未声明时一切如旧);agent 新增 `metric_target_progress` 工具与提示词路由第 11 条。
- 非 UI 改动,uitest 未执行。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | REST /subscriptions 不暴露 watch 参数(threshold/watch_mode),model 模式仅 CLI/引擎可用 | api_subscriptions.py SubscriptionCreateRequest | 既有边界,本批未扩 | API 编排方建不了异动订阅 | 需要时给 request model 加三个字段即可 |
| 低 | ratio 指标不支持 targets(目标是水平值,投影不可加总) | metrics.py _parse_targets | 设计取舍,校验器显式拒绝 | 退款率类指标无法挂目标 | 如有需求,completion 用当期比率/目标值、不做投影 |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
