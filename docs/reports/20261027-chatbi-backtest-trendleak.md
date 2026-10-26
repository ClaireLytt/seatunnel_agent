# 批次结果报告:chatbi 告警回测 + 趋势泄漏修复(2026-10-27)

## 批准依据

> 用户对继续开发回复:"go on";本批取候选"告警规则回测"+ 上批遗留"dod/wow 断更探测"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中高 | `backtest_watch` + CLI `t2s-sub backtest <id> --days N`:1 条序列 SQL + 纯 Python 重放告警规则(dod/wow/model 三模式),输出会触发的日期明细与告警率,供上线前调参 | subscriptions.py, cli_cmds/text2sql.py | 本批 |
| 高 | **预测模型缺陷修复(回测测试暴露)**:强星期周期序列会把形态泄漏进 OLS 趋势斜率(周末低值集中周尾 → 斜率 -0.55,预期 90.4 而非 100,model 告警系统性误报)。修法:趋势↔星期偏移回拟合迭代至收敛;纯周期序列斜率归 0、预测恢复精确 | forecast.py | 本批 |
| 中 | 上批遗留:dod/wow 模式昨日值为 0 时先探表新鲜度,管道滞后 → no_data 断更提示,不发 -100% 假告警 | subscriptions.py | 本批 |

新增测试 4 条:回测对照实验(工作日100/周末50+真尖峰:model 只报尖峰 1 次,dod 20% 阈值误报 >3 次)/ 未知指标报错 / dod 断更保护 / 趋势泄漏锁定测试(纯周期序列 slope≈0、yhat≈100)。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 107 source files
python -m pytest tests/test_text2sql_forecast.py -q -> 35 passed in 1.51s
python -m pytest -q          -> 3431 passed, 1 skipped, 243 deselected in 141.84s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

证据链:回测测试先失败(model 9 次告警,预期 1)→ 探针脚本定位 slope=-0.547 / yhat=90.42(节假日为空,排除日历因素)→ 一次回拟合不足(99.41,偏差仍大于窄带)→ 迭代收敛后 1 次告警,全部通过。

## 前后差异

- 测试:3427 → 3431 passed(+4)。
- 行为:`forecast_metric` 与 model watch 对强周期指标的预测从系统性偏差(约 -10%)变为精确;纯线性趋势序列结果不变(既有精确恢复测试全过)。新增 backtest CLI;dod/wow 获得断更保护。
- 非 UI 改动,uitest 未执行。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 回测对缺日的处理假定历史数据完整(additive 缺日按 0 重放),不区分历史断更日 | subscriptions.py backtest_watch | 历史断更已无法事后探测 | 历史有断更时回测会多算几次"告警" | 文档已注明;可选:跳过全 0 日 |
| 低 | 大分区表 MAX(time_column) 开销(上批遗留,未动) | _max_time_value | 同上批 | 同上批 | 分区表读最大分区名 |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
