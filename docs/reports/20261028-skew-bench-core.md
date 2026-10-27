# 批次结果报告:skew-bench-core(2026-10-28)

## 批准依据

> 用户:"go on"(对「skew-bench 静态检测器基准」两批提案的批准,本批为批次 1:语料 + 评测核心)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 标注语料:23 例(13 条规则全覆盖 + 7 个"必须干净"的负样本),期望为精确集合;从规则单测 SQL 策展而来,三处偏差逐一人工裁定(join 带 DS013 合理、DS008 对 rand 不重复报是既有行为)并注释 | examples/skew_bench/cases.yaml | 本批次 |
| 高 | 评测核心:load_corpus / run_bench(micro P/R/F1 + 逐例漏报/误报)/ render_bench(zh/en);门槛 min_f1 随语料落盘 | agents/data/data_skew/bench.py | 本批次 |
| 高 | 测试:语料全绿守卫(任何规则改动引起整卷偏移即红,带逐例 diff)、规则全覆盖断言、评分三态(TP/FP/FN)单测 | tests/test_data_skew.py | 本批次 |

## 验证结果

```
ruff check src tests                 -> All checks passed!
mypy                                 -> Success: no issues found in 175 source files
pytest tests/test_data_skew.py -q    -> 214 passed in 8.09s
pytest -q(全量)                     -> 3519 passed, 1 skipped, 249 deselected, 2 warnings in 146.59s
基准实跑                             -> 23 cases · precision 1.000 · recall 1.000 · F1 1.000 (gate 1.000)
python scripts/check_workflow.py     -> 提交后全 [PASS](见对话)
```

无 UI 改动,未跑 uitest。

## 前后差异

- 测试类:test_data_skew.py 212 → 214;全量 3517 → 3519 passed。
- 行为:检测器此前只有逐条单测;现在任何规则改动都会在 23 例整卷上算 P/R/F1,偏移立即被 test_bench_corpus_is_green 以逐例 diff 报红。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | 尚无 CLI 门面(`skew-bench --gate` / -F json)与文档 | bench.py 无调用方(仅测试) | 拆批 | 流水线暂不可直接跑基准 | 批次 2 |

## 未执行的步骤

- uitest:无 UI 改动,不要求。
