# 批次结果报告:pipeline-ops 套件 CLI 入口(2026-10-31)

## 批准依据

> "think about new functions"（第七轮：补齐 Web/MCP/CLI 三入口中缺失的 CLI）

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | 五个 CLI 子命令 dagopt/rerun/backfill-sql/sync-strategy/pipe-migrate | src/seatunnel_agent/cli_cmds/pipeline_ops.py | (本批) |
| 中 | CLI 测试(CliRunner,markdown/json/落盘/缺参报错) | tests/test_pipeline_ops_cli.py | (本批) |
| 低 | 指南入口表补 CLI 列与通用参数 | docs/pipeline_ops_guide.md | (本批) |

## 验证结果

```
pytest tests/test_pipeline_ops_cli.py -q -> 5 passed
seatunnel-agent dagopt -f examples/dagopt_demo/dag.json --lang en -> 报告正常
seatunnel-agent rerun -f ... --failed clean_orders -F json -> JSON 正常
seatunnel-agent backfill-sql --plan '<计划JSON>' -> 规格骨架正常
seatunnel-agent sync-strategy / pipe-migrate -> 报告正常
ruff check src/seatunnel_agent tests -> All checks passed!
python -m mypy src/seatunnel_agent/cli_cmds/pipeline_ops.py -> Success: no issues found
python scripts/check_workflow.py --range origin/main...HEAD ->
  [PASS] AI 署名: 无 AI 署名(范围 origin/main...HEAD)
  [PASS] 工作区: 工作区干净
  [PASS] 报告落盘: 代码改动已附带落盘报告
  [PASS] 报告含验证输出: 报告含 check_workflow 输出
  [PASS] floor: 无作弊变绿改动(范围 origin/main...HEAD)
  [PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/main...HEAD)
```

## 前后差异

- 五个 agent 补齐第三个入口:Web 页 + MCP 工具 + CLI 子命令。
- `-F json` 使五个分析都可直接接入 CI/脚本;`--plan` 支持命令行完成
  计划→规格桥接。
