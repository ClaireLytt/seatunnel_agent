# 批次结果报告:chatbi 指标树分解(2026-10-27)

## 批准依据

> 用户对第十一轮候选(建议"1(指标树)")回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 语义层:`tree: [traffic, cvr, aov]` 字段(2–5 个因子,去重),store 级校验(因子须已定义、禁自引用);tree 纳入口径变更追溯 CALIBER_FIELDS | metrics.py | 本批 |
| 高 | 数学:`tree_factor_split` 对数(LMDI 式)分解——`Δln(父) = ΣΔln(因子) + 残差`,份额+残差恒等 100%(自检);≤0 值/父无变化显式返回 None | attribution.py | 本批 |
| 高 | 工具 `tree_attribution`:因子两期总量(2×(1+K) 条 SQL)→ 分解 → 份额最大的 additive 因子自动维度归因;日期入参与 run_attribution 一致(抽出共享 `_attribution_ranges`);qlog kind=tree;提示词第 13 条(有树先走树) | tools_metric.py, tools.py, prompts.py | 本批 |
| — | 指南"指标树分解"节 | docs/chat_bi_guide.md | 本批 |

新增测试 4 条:恒等式纯函数(精确树残差≈0、份额排序、无变化/非正值拒绝)/ 解析与校验(自引用、未定义、因子过少)/ sqlite 端到端(gmv=order_cnt×aov:单量份额 0%、客单价 100%、残差 0、check_ok)/ 未声明树报错。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 172 source files
python -m pytest tests/test_text2sql_metrics.py -q -> 93 passed in 10.50s
python -m pytest -q          -> 3458 passed, 1 skipped, 243 deselected in 152.24s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3454 → 3458 passed(+4)。
- 行为:声明了 tree 的指标,"为什么涨/跌"先回答因子层(流量还是转化)再下钻维度;未声明 tree 的一切如旧。
- 非 UI 改动,uitest 未执行。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | tree_attribution 未上 REST/MCP 门面 | 本批范围 | 门面是薄壳,待功能稳定 | 编排/IDE 暂不可用 | 照 forecast/target 模式各加一壳(半小时) |
| 低 | 残差大时(树不精确)LLM 叙述依赖提示词自觉 | tree_factor_split residual | 已输出 residual_share_pct | 可能忽略残差 | 工具描述已要求提及;观察后定 |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
