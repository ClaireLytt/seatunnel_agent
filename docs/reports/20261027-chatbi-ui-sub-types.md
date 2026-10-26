# 批次结果报告:UI 露出·订阅三类型(2026-10-27)

## 批准依据

> 用户对"启动 UI 露出"回复:"go on";截图交付验收后用户回复:"go on"(视为验收通过)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | REST `/subscriptions` 创建请求补齐 watch/freshness/digest 字段(threshold_pct/watch_mode/max_lag_days/metrics),透传 store.add(校验沿用) | api_subscriptions.py | 本批 |
| 高 | React 订阅表单:五类型单选(metric/收藏/异动监控/数据断更/经营日报),条件字段(watch 模式下拉+阈值,model 模式隐藏阈值;断更滞后天数;日报指标清单);列表"来源"列区分展示(⚡/⏰/指标清单) | SubscriptionsView.tsx, api.ts | 本批 |
| — | i18n 中英 12 键 | i18n.ts | 本批 |

## 验证结果

```
npm run lint --workspace text2sql -> 通过
npm run build --workspace text2sql -> ✓ built in 11.14s(dist 已重建)
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 174 source files
python -m pytest -q          -> 3466 passed, 1 skipped, 243 deselected in 162.90s
uitest smoke(真浏览器)     -> PASS 16 · FAIL 0 · ERROR 0(runs/20261027_024658/report.html)
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

真浏览器截图(build/subs_form_{watch,digest,freshness}.png,gitignored)已在对话中交付,用户验收通过;截图脚本为一次性探针,已清理。

## 前后差异

- UI:订阅侧边栏从两类型(metric/favorite)变五类型,引擎侧全部订阅能力对 UI 用户可见可建。
- 测试:3466 passed 持平(REST 字段有既有 create 流测试覆盖路径;表单为前端渲染逻辑,由 smoke+截图验证)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 单选标签 "metrics" 为既有 i18n 原值(英文残留) | 截图 | 存量 | 观感 | 路线图第 4 批顺手修 |
| 中 | uitest 的 chatbi 用例未覆盖新表单字段 | cases/chatbi.yaml | 本批用 smoke+截图验收 | 新表单无自动回归 | 路线图后续批补 1-2 条用例 |

## 未执行的步骤

- 新表单的 uitest 专项用例:未执行(见遗留)。
- 其余无。
