# 批次结果报告:coverage_map 补洞命令清单 E2(2026-10-31)

## 批准依据

> "go on"(执行队列头:搁置的 E2 增强)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | CM001 裸奔表在报告尾部附可直接运行的补洞命令(dqrulegen + contractgen 提示),zh/en 文案 | agents/data/coverage_map/{report,i18n}.py | (本批) |
| 中 | 回归测试:每张裸奔表一条命令行 | tests/test_coverage_map.py | (本批) |

## 验证结果

```
python -m pytest tests/test_coverage_map.py -q -> 12 passed in 2.63s
ruff check src tests -> All checks passed!
```

```
(gate 输出占位,提交后回填)
```

## 前后差异

- coverage_map 报告:发现裸奔表后只点名 → 点名并给出闭环命令;测试 11 → 12 条。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

E3(orchestrator "topic 接入三连" 预设)待下一批。
