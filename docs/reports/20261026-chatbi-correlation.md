# 批次结果报告:chatbi 多指标相关性(2026-10-26)

## 批准依据

> 用户对"下一步可做候选 3(多指标相关性)或 4(看板 digest)"回复:"go on",取排序在前的候选 3。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中高 | 新工具 `correlate_metrics`:两指标日序列 Pearson r(2 条确定性 SQL)+ ±7 天滞后扫描(lag>0 = metric_a 领先);additive 缺日补 0,ratio 缺日丢对;对齐 <7 天拒绝,零方差显式标记;qlog kind=correlation | tools_metric.py, tools.py | 本批 |
| — | 提示词路由第 12 条(相关≠因果,"为什么"仍引导归因) | prompts.py | 本批 |
| — | 指南"多指标相关性"章节 | docs/chat_bi_guide.md | 本批 |

新增测试 4 条:完美线性相关 r=1 / 领先滞后检测(b=shift(a,1) → best_lag=+1 且 lag0 显著更弱)/ 同名与未知指标报错 / 零方差标记,全部 sqlite 端到端。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 107 source files
python -m pytest tests/test_text2sql_forecast.py -q -> 34 passed in 1.49s
python -m pytest -q          -> 3422 passed, 1 skipped, 243 deselected in 143.45s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3418 → 3422 passed(+4)。
- 行为:新增 `correlate_metrics` 工具与提示词第 12 条;其余路径不变。
- 非 UI 改动,uitest 未执行。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 滞后扫描对强趋势序列可能把趋势误读为领先关系(未去趋势) | tools_metric.py _tool_correlate_metrics | 保持零依赖确定性,去趋势会改变 r 口径 | 共同上涨的两指标 lag 结果意义有限 | 如需要,可加 `detrend=true` 选项对差分序列算 r |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
