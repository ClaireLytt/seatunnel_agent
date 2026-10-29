# 批次结果报告:孤儿豁免清单 + 治理历史统计(2026-10-29)

## 批准依据

> 用户对打包节奏"3+4 一批"所在计划回复"go on"(上批 1+2 完成后继续)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 孤儿豁免:analyzer 三入口新增 exempt(fnmatch 通配);命中进 report.exempted 而非 findings;CLI `hygiene --exempt FILE`(YAML tables: [...],非法结构报错);REST exempt: list[str];报告摘要行附 exempted N | lineage_hygiene/{analyzer,report,api}.py, cli_cmds/checks.py | 本批 |
| 高 | 历史落档:HygieneLogger(logs/hygiene.jsonl)与 MetaQualityLogger(logs/metaquality.jsonl),复用 JsonlLog 轮转;CLI 与 REST 两路都记 source | lineage_hygiene/history.py, metadata_quality/history.py, 两 api.py | 本批 |
| 高 | 趋势 CLI:`hygiene-stats`(孤儿 X → Y)与 `metaquality-stats`(注释覆盖 X% → Y%),体例同 impact-stats | cli_cmds/checks.py | 本批 |
| 高 | 新测试 5 项(豁免/豁免文件门禁/非法清单/两 agent 的落档+stats) | tests/test_lineage_hygiene.py, tests/test_metadata_quality.py | 本批 |

## 验证结果

```
pytest tests/test_lineage_hygiene.py tests/test_metadata_quality.py -q -> 30 passed
pytest -q                                      -> 3572 passed, 1 skipped, 256 deselected
ruff check src tests                           -> All checks passed!
mypy                                           -> Success: no issues found in 176 source files
python scripts/check_workflow.py --range origin/main...HEAD ->
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/main...HEAD)
```

## 前后差异

- hygiene 的孤儿误报(外部 BI 直读)有了正规出口;上上批遗留"豁免清单"关闭。
- 治理双子对齐套件 `*-stats` 惯例(impact/lineage/skew 之后第 4、5 个),治理工作可度量:「孤儿表 12 → 8」。

## 未解决问题 / 遗留清单

无。治理线(pii / hygiene / metaquality)至此全部完整:四表面+编排器+历史趋势+豁免机制。

## 未执行的步骤

无。
