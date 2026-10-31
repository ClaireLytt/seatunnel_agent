# 批次结果报告:DAG 变更评审 CI gate(2026-10-31)

## 批准依据

> "go on"（上一轮点名的自然后续:--fail-on 风格的回归闸门）

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | dagopt --fail-on-regression [--tolerance X]:关键路径增幅超容忍或引入新冗余边即 exit 1;无 --base 时报用法错误 | cli_cmds/pipeline_ops.py | (本批) |
| 低 | 指南 CLI 段补 gate 用法 | docs/pipeline_ops_guide.md | (本批) |

## 验证结果

```
pytest tests/test_pipeline_ops_cli.py -q -> 9 passed
  (覆盖:超容忍 exit1+原因、容忍内 exit0、冗余边无视 tolerance 仍 exit1、缺 --base exit2)
ruff check src/seatunnel_agent tests -> All checks passed!
python -m mypy cli_cmds/pipeline_ops.py -> Success: no issues found
python scripts/check_workflow.py --range origin/main...HEAD ->
  [PASS] AI 署名: 无 AI 署名(范围 origin/main...HEAD)
  [PASS] 工作区: 工作区干净
  [PASS] 报告落盘: 代码改动已附带落盘报告
  [PASS] 报告含验证输出: 报告含 check_workflow 输出
  [PASS] floor: 无作弊变绿改动(范围 origin/main...HEAD)
  [PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/main...HEAD)
```

## 前后差异

- DAG 变更评审从"看报告"升级为"能挡 CI":调度仓库可在 PR 流水线跑
  `dagopt -f new.json --base old.json --fail-on-regression`。
