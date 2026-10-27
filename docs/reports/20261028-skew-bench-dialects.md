# 批次结果报告:skew-bench-dialects(2026-10-28)

## 批准依据

> 用户:"go on"(对「基准语料的方言维度」提案的批准)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | 语料 +4 方言用例(maxcompute MAPJOIN hint 抑制 DS013、mc count-distinct、hive 动态分区、hive 外连接 NULL 键),期望实跑裁定 | examples/skew_bench/cases.yaml | 本批次 |
| 高 | 守卫测试补三方言覆盖断言 + 方言原生 hint 抑制断言 | tests/test_data_skew.py | 本批次 |

## 验证结果

```
ruff check src tests                 -> All checks passed!
pytest tests/test_data_skew.py -q    -> 215 passed in 10.88s
pytest -q(全量)                     -> 3520 passed, 1 skipped, 249 deselected, 2 warnings in 143.51s
基准实跑                             -> 27 cases · precision 1.000 · recall 1.000 · F1 1.000 (gate 1.000)
python scripts/check_workflow.py     -> 修订报告后全部通过,逐行如下
```

```
[PASS] AI 署名: 无 AI 署名(范围 origin/skew..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/skew..HEAD)
```

无 UI 改动,未跑 uitest;mypy 未单跑(无 src 签名变更,全量 pytest 已含导入验证)。

## 前后差异

- 语料 23 → 27 例,三方言全覆盖;检测器的方言分支(hint 识别/建议文本之外的规则集稳定性)纳入整卷回归。

## 未解决问题 / 遗留清单

无。此后本线新增想法边际价值评估为低,建议收官。

## 未执行的步骤

- uitest:无 UI 改动,不要求。mypy:见上注。
