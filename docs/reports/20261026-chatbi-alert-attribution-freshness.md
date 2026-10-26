# 批次结果报告:chatbi 告警自动归因 + 数据新鲜度(2026-10-26)

## 批准依据

> 用户对第二轮候选清单(建议"1+2 一个批次")回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 告警自动归因:additive 指标触发告警时自动跑 run_attribution(昨日 vs 参照期),卡片附 Top3 成员贡献率(恒等式口径)与新增/消失标记;ratio 保留原两日对比;model/wow 的下钻参照期统一为上周同日 | subscriptions.py | 本批 |
| 高 | 新订阅类型 `freshness`:MAX(time_column) 落后超 max_lag_days 告警(比率自动查分子/分母两表);CLI `--freshness --max-lag-days` | subscriptions.py, cli_cmds/text2sql.py | 本批 |
| 高 | 假告警修复:model watch 昨日无行时先探 MAX(dt),表未更新→no_data 断更提示,不再按 0 计算触发 -100% 假告警 | subscriptions.py | 本批 |
| — | 指南:freshness 示例、告警归因与断更说明 | docs/chat_bi_guide.md | 本批 |

新增测试 5 条:断更假告警抑制 / 告警卡含归因贡献率(web 暴涨场景) / freshness 告警与静默 / freshness 校验,全部 sqlite 端到端。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 107 source files
python -m pytest tests/test_text2sql_subscriptions.py -q -> 42 passed in 7.73s
python -m pytest -q          -> 3427 passed, 1 skipped, 243 deselected in 140.13s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

调试记录:归因接入初版误用 `attri.breakdowns`(实际字段 `dimensions`),被 best-effort except 吞掉导致测试暴露;最小复现脚本定位后修正,临时探针 db 已清理。

## 前后差异

- 测试:3422 → 3427 passed(+5)。
- 行为:additive 告警卡从"裸 delta Top3"升级为"贡献率 Top3 + 新增/消失标记";管道滞后日从"假 -100% 告警"变为"断更 no_data";新增 freshness 订阅类型(存量订阅不受影响)。
- 非 UI 改动,uitest 未执行。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | dod/wow 模式缺日仍按 _total 的"无行=0"口径,未接断更探测(仅 model 模式接了) | subscriptions.py _total | 本批范围控制 | dod/wow 在管道滞后日仍可能假告警 | 同一探测逻辑可平移到 _total 为 0 时 |
| 低 | freshness 的 MAX() 对大分区表可能全扫(取决于引擎元数据优化) | _max_time_value | 通用 SQL 实现 | Hive 大表上开销不小 | 分区表可改读最大分区名(partition 模块已有能力) |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
