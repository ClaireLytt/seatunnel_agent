# 批次结果报告:监控与飞轮清尾(2026-10-27)

## 批准依据

> 用户对第十八轮候选(清尾三条)回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中高 | 告警历史:watch 告警/恢复各落一条 qlog 事件(kind=alert/alert_recovered,best-effort 不碍告警);`metrics health` 的 7 天统计新增真实"告警次数"(此前只能看当前是否告警中) | subscriptions.py, health.py, cli_cmds/text2sql.py | 本批 |
| 中 | 日序列共享缓存:`fetch_daily_series` 进程内 TTL 缓存(默认 600s,`T2S_SERIES_CACHE_TTL=0` 关闭),覆盖窗口的新鲜条目直接切片——model watch 与 digest 改走此入口,晨间同指标并发只打一次库 | subscriptions.py | 本批 |
| — | 第 3 条(`promote --require-feedback`)**经查无效结案**:👍 过的问题本就直接入示例库,promote 只处理无示例问题,"只收 👍"是空集;真实防线仍是默认 dry-run | — | 不改代码 |

新增测试 2 条:告警→恢复两事件落 qlog;缓存命中(宽窗口 1 次 SQL、子窗口零 SQL 切片、TTL=0 必发 SQL)。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 174 source files
python -m pytest tests/test_text2sql_subscriptions.py -q -> 58 passed in 9.58s
python -m pytest -q          -> 3466 passed, 1 skipped, 243 deselected in 158.40s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3464 → 3466 passed(+2)。
- 行为:健康页多出真实告警计数;订阅晨间突发的重复序列查询消失;digest/watch 的查询语义不变(测试全过)。

## 未解决问题 / 遗留清单

无(本功能线)。

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
