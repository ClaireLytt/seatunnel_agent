# 批次结果报告:迁移评估的 LLM 改写建议(2026-10-31)

## 批准依据

> "go on"（开启此前预留的 LLM 增强层,沿 data_skew 的 use_llm 模式）

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | pipemigrate LLM 改写建议:对风险最大的任务(上限 3 个)请求目标引擎等价写法与代码草案 | pipeline_migrate/advisor_llm.py | (本批) |
| 中 | API `llm: true` 开关(无 key → 503)与 CLI `--llm` 开关 | pipeline_migrate/api.py, cli_cmds/pipeline_ops.py | (本批) |
| 中 | 接线测试(LLM 调用打桩,验证风险任务筛选、报告拼接、默认关闭) | tests/test_pipeline_migrate.py | (本批) |

## 验证结果

```
pytest tests/test_pipeline_migrate.py -q -> 12 passed
pytest tests/test_pipeline_ops_cli.py -q -> 8 passed
ruff check src/seatunnel_agent tests -> All checks passed!
python -m mypy pipeline_migrate + cli -> Success: no issues found in 9 source files
python scripts/check_workflow.py --range origin/main...HEAD ->
  [PASS] AI 署名: 无 AI 署名(范围 origin/main...HEAD)
  [PASS] 工作区: 工作区干净
  [PASS] 报告落盘: 代码改动已附带落盘报告
  [PASS] 报告含验证输出: 报告含 check_workflow 输出
  [PASS] floor: 无作弊变绿改动(范围 origin/main...HEAD)
  [PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/main...HEAD)
```

## 前后差异

- 确定性核心不变;LLM 层严格 opt-in,默认路径零行为变化(有测试守住)。
- 成本有界:只取风险数×工作量排序最高的前 3 个任务,脚本截断 8k 字符。
