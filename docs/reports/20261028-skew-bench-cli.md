# 批次结果报告:skew-bench-cli(2026-10-28)

## 批准依据

> 用户:"go on"(skew-bench 两批提案的批次 2:CLI 门面 + 门禁 + 文档)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `seatunnel-agent skew-bench [--corpus] [--gate] [-F json] [--lang]`:默认语料实跑 P/R/F1;--gate 低于 baseline.min_f1 退出 1;json 带逐例 failures | src/seatunnel_agent/cli_cmds/skew.py | 本批次 |
| 中 | 指南 CLI 节 + README 双语示例各补一行 | docs/data_skew_guide.md, README.md | 本批次 |
| 高 | CLI 测试:绿语料过门禁、坏语料门禁退出 1(带逐例 diff)、json 可解析 | tests/test_data_skew.py | 本批次 |

## 验证结果

```
ruff check src tests                 -> All checks passed!
mypy                                 -> Success: no issues found in 175 source files
pytest tests/test_data_skew.py -q    -> 215 passed in 11.84s
pytest -q(全量)                     -> 3520 passed, 1 skipped, 249 deselected, 2 warnings in 146.64s
python scripts/check_workflow.py     -> 提交后全 [PASS](见对话)
```

无 UI 改动,未跑 uitest。

## 前后差异

- 测试类:test_data_skew.py 214 → 215;全量 3519 → 3520 passed。
- 行为:基准此前只能 import 跑;现在 `skew-bench --gate` 可直接挂流水线(与 t2s-bench 同款待遇)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 未加进 CI workflow(test_bench_corpus_is_green 已在 pytest 中兜底同一回归) | lint.yml 无 skew-bench job | pytest 守卫已覆盖,CI 加 job 属重复 | 无 | 如想要独立 CI 信号再加 |

## 未执行的步骤

- uitest:无 UI 改动,不要求。
