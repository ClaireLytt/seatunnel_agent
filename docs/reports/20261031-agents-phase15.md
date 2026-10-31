# 批次结果报告:sync-strategy 风险闸门(2026-10-31)

## 批准依据

> "think about new functions"（第二十二轮：inventory-as-code 的 CI gate）

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | RISK_CODES 常量固化全部风险码（gate 校验的唯一来源） | sync_strategy/advisor.py | (本批) |
| 中 | sync-strategy --fail-on-risk CODE[,CODE]：命中即 exit 1 并逐表列出；拼错码报用法错误并提示可用集合 | cli_cmds/pipeline_ops.py | (本批) |
| 低 | 指南 CLI 段补用法 | docs/pipeline_ops_guide.md | (本批) |

## 验证结果

```
pytest tests/test_pipeline_ops_cli.py tests/test_sync_strategy.py -> 25 passed
  (覆盖:demo 绿、分钟级无 binlog 命中 exit1、拼错码 exit2 带可用集合)
ruff check src/seatunnel_agent tests -> All checks passed!
python -m mypy cli + sync_strategy -> Success: no issues found in 11 source files
python scripts/check_workflow.py --range origin/main...HEAD ->
  [PASS] AI 署名: 无 AI 署名(范围 origin/main...HEAD)
  [PASS] 工作区: 工作区干净
  [PASS] 报告落盘: 代码改动已附带落盘报告
  [PASS] 报告含验证输出: 报告含 check_workflow 输出
  [PASS] floor: 无作弊变绿改动(范围 origin/main...HEAD)
  [PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/main...HEAD)
```

## 前后差异

- 表特征清单可当代码管:PR 里新加"分钟级时延但没 binlog"的表会被
  CI 逐表点名拦下,而不是上线后才发现同步追不上。
