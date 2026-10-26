# 批次结果报告:UI 露出·回测按钮(2026-10-27)

## 批准依据

> 用户对"提交当前批 → 做路线图 2"方案回复:"go on"(截图验收通过)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中高 | REST `POST /subscriptions/{id}/backtest?days=N`:仅 watch 订阅(否则 400),schema 走服务端 env,凭据服务端解析,days 夹在 7–365 | api_subscriptions.py | 本批 |
| 中高 | UI:watch 行 📈 按钮 + 结果面板(评估天数/告警次数/告警率/窗口/模式 + 前 10 条明细,model 模式带预期与 95% 区间);i18n 中英 3 键 | SubscriptionsView.tsx, api.ts, i18n.ts | 本批 |

新增测试 1 条:REST 回测端到端(14 天平稳 + 昨日尖峰 → model 模式恰 1 次告警、日期正确;非 watch 订阅 400)。

## 验证结果

```
python -m pytest tests/test_t2s_subscriptions_api.py -q -> 9 passed
npm run lint/build --workspace text2sql -> 通过,dist 重建
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 174 source files
python -m pytest -q          -> 3467 passed, 1 skipped, 243 deselected in 162.98s
真浏览器截图                -> build/subs_backtest.png(对话中交付,面板显示"评估 8 天,
                               会触发 1 次告警 (12.5%)",明细 500(预期 150 [106.09, 193.91]));
                               截图探针脚本已清理
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3466 → 3467 passed(+1)。
- UI:watch 订阅的阈值/模式调参从 CLI 搬进浏览器,一键看历史告警频率。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 回测 days 在 UI 固定 90(REST 可传) | SubscriptionsView | 保持面板简洁 | 调窗口需 REST/CLI | 需要时加个输入框 |

## 未执行的步骤

- uitest 专项用例:未执行(REST 测试 + 真浏览器截图覆盖;与上批遗留合并待补)。
- 其余无。
