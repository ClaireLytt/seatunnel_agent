# 批次结果报告:skew-sink-drift(2026-10-28)

## 批准依据

> 用户:"go on"(对「sink 端键纳入漂移体系」提案的批准)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `sink_key_section(log_source=...)`:有可解析 sink 表时,逐键以 log_splitkey 落历史(含 top1_value);无 log_source 行为不变 | agents/data/data_skew/splitkey.py | 本批次 |
| 高 | 三入口接通:CLI 单配置(cli)、REST /splitkey(api)、MCP skew_split_key(mcp) | cli_cmds/skew.py, data_skew/api.py, mcp_server.py | 本批次 |
| 高 | 测试:三次实测落 3 条记录(表/键/判定/top1 值断言)、sink 表获得 skew-drift 判定、默认不落历史 | tests/test_data_skew.py | 本批次 |

由此 sink 表自动获得既有机制:趋势行、漂移基线/告警/恢复卡、skew-stats 汇总。

## 验证结果

```
ruff check src tests                 -> All checks passed!
mypy                                 -> Success: no issues found in 175 source files
pytest tests/test_data_skew.py -q    -> 211 passed in 7.78s
pytest -q(全量)                     -> 3515 passed, 1 skipped, 249 deselected, 2 warnings in 144.50s
python scripts/check_workflow.py     -> 修订报告后全部通过,逐行如下
```

```
[PASS] AI 署名: 无 AI 署名(范围 origin/skew..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/skew..HEAD)
```

无 UI 改动,未跑 uitest。

## 前后差异

- 测试类:test_data_skew.py 210 → 211;全量 3514 → 3515 passed。
- 行为:sink 端分布键此前只在单次报告里出现;现在与 source 键同等进入趋势/漂移/统计体系。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 无 sink 表标识(spec.table 为空)的 sink 键不落历史 | splitkey.py log 分支 continue | 趋势需要稳定身份,不猜 | 此类键仍只有单次报告 | 配置里写明 table 即可获得 |

## 未执行的步骤

- uitest:无 UI 改动,不要求。
