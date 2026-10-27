# 批次结果报告:skew-drift-core(2026-10-27)

## 批准依据

> 用户:"go on"(对「批次 1(核心):`data_skew/drift.py`——时间序列读取、基线/漂移计算、阈值判定;单测」提案的批准,并在拆票后再次 "go on")。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | drift 核心:splitkey 历史基线(中位数)对比,top1/null/ndv 漂移判定,drift/stable/insufficient 三态 | src/seatunnel_agent/agents/data/data_skew/drift.py | 本批次 |
| 高 | 7 个单测:insufficient、未测量记录不计数、stable、top1 上涨、null 上涨 + ndv 坍缩、ndv 降幅低于阈值 | tests/test_data_skew.py | 本批次 |
| 中 | spec 与拆票落盘 | .scratch/skew-drift/(spec.md, issues/01-03) | 本批次 |

## 验证结果

```
ruff check src tests scripts              -> All checks passed!
mypy                                      -> Success: no issues found in 175 source files
pytest tests/test_data_skew.py -q         -> 185 passed in 6.31s
pytest -q(全量)                          -> 3488 passed, 1 skipped, 247 deselected, 2 warnings in 177.62s
python scripts/check_workflow.py          -> (输出见下方追加)
```

无 UI 改动,未跑 uitest。

## 前后差异

- 测试类:tests/test_data_skew.py 178 → 185 passed(+7 drift 用例);全量 3481 → 3488 passed。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | drift 仅有核心函数,无任何入口(CLI/splitkey 尾行/webhook/REST/前端) | drift.py 无调用方(grep compute_drift 仅 tests) | 按拆票 01→02→03 串行 | 功能尚不可被用户触达 | 票 02、03 |
| 低 | 阈值为固定常量,不可配置 | drift.py TOP1_DRIFT_PP 等 | spec v1 明确"保持简单" | 特殊表无法调灵敏度 | 需求出现再做 |

## 未执行的步骤

- uitest:本批次无 UI 改动,按第 8 节规则不要求。
