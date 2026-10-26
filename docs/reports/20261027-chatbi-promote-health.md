# 批次结果报告:chatbi 示例批量固化 + 指标健康页(2026-10-27)

## 批准依据

> 用户对第七轮候选清单(建议"1+2 一批")回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `promote_candidates` + CLI `t2s-examples promote`:从 qlog 找"高频(≥min_count)、成功、尚无示例"的问题,带其最近一次成功 SQL 批量固化(默认 dry-run,`--yes` 入库,source=promoted)——飞轮从可见到可执行 | examples.py, cli_cmds/text2sql.py | 本批 |
| 中高 | `metric_health` + CLI `metrics health`:每指标一行 新鲜度(滞后天数)/告警中(自哪天)/7天查询与失败/月目标达成/订阅数,红黄绿排序;各信号 best-effort,单指标故障不遮蔽其他行 | health.py(新), cli_cmds/text2sql.py | 本批 |
| — | 指南两节 | docs/chat_bi_guide.md | 本批 |

新增测试 2 条:promote 候选(最新成功 SQL 胜出/已固化排除/低频排除/失败排除/非交互排除)/ health 汇总(新鲜 lag=0、7天统计含窗口过滤、月达成 2.1%、告警中红且排最前、有失败黄)。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 107 source files
python -m pytest tests/test_text2sql_examples.py tests/test_text2sql_subscriptions.py -q -> 71 passed in 6.37s
python -m pytest -q          -> 3450 passed, 1 skipped, 243 deselected in 152.89s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

说明:mypy 的 pyproject files 白名单不含 text2sql 包(存量边界),新模块 health.py 与全包一致不在门禁内;单测覆盖其全部分支逻辑。

## 前后差异

- 测试:3448 → 3450 passed(+2)。
- 行为:固化高频问题从"看报告手工搬运"变为一条命令;治理侧从拼四个数据源变为 `metrics health` 一张红黄绿表。
- 非 UI 改动,uitest 未执行。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | promote 固化的 SQL 未经人工复核即进语义缓存(qlog success ≠ 结果正确) | t2s-examples promote | dry-run 默认已是复核点 | 错误 SQL 可能被固化(👎 可退出) | 文档已示 dry-run 先看;可选加 --require-feedback 只收 👍 过的 |
| 低 | mypy 白名单不含 text2sql 包(存量) | pyproject.toml files | 渐进式类型化策略 | 新模块同样不受 mypy 门禁 | 后续批次可将 text2sql 增补进白名单(floor 允许扩大) |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
