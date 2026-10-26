# 批次结果报告:chatbi 卡片 i18n + qlog 洞察(2026-10-27)

## 批准依据

> 用户对第六轮候选清单(建议"1+2 一批")回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中(缺陷) | 订阅卡片 i18n:`_CARD_STRINGS` zh/en 文案字典 + `_card_text`,覆盖 失败卡/断更卡/恢复卡/阈值告警/模型基线告警/贡献标注/digest 全套;按订阅 `lang` 渲染,zh 输出逐字节不变(既有断言卡片原文的测试全过) | subscriptions.py | 本批 |
| 中高 | qlog 洞察 `insights()` + CLI `t2s-qlog-stats`:高频问题×是否已固化示例(=语义缓存覆盖率)、失败聚类(含末次错误)、慢查询 Top、来源分布;非交互行([subscription] 等)不进问题榜 | qlog.py, cli_cmds/text2sql.py | 本批 |
| — | 指南两处 | docs/chat_bi_guide.md | 本批 |

新增测试 3 条:en digest 卡(断言英文文案且无中文残留)/ en 模型告警卡 / insights 纯函数(覆盖率 66.7% 恒等、失败聚类、慢查询、来源)。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 107 source files
python -m pytest tests/test_text2sql_subscriptions.py -q -> 53 passed in 5.82s
python -m pytest -q          -> 3448 passed, 1 skipped, 243 deselected in 155.99s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3445 → 3448 passed(+3)。
- 行为:`lang=en` 订阅从收中文卡变为收英文卡(zh 默认输出逐字节不变);新增 `t2s-qlog-stats` 命令,把"哪些高频问题值得固化成零成本缓存"变成一条命令可见。
- 非 UI 改动,uitest 未执行。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 卡片 emoji 标题(⚠️/✅/📊/⏰)与 metric/favorite 成功卡表头未进 i18n(语言无关或由 render_card_markdown 直出列名) | subscriptions.py | 表头是数据列名,emoji 无语言 | 可忽略 | 无需处理 |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
