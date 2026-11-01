# 批次结果报告:迁移燃尽监测(2026-10-31)

## 批准依据

> "go on"（第二十六轮：history 模式推广到 pipe-migrate）

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | _track_history 泛化为通用 jsonl 助手(entry + worse_key),dagopt 改用 | cli_cmds/pipeline_ops.py | (本批) |
| 中 | pipe-migrate --history:每次盘点记录 jobs/效力分布/SeaTunnel 目标数/风险总数,打印燃尽对比,任务数回升黄字警示 | cli_cmds/pipeline_ops.py | (本批) |

## 验证结果

```
pytest tests/test_pipeline_ops_cli.py -> 12 passed
  (燃尽覆盖:首次记录、删一个任务后 jobs 6→5 与 to_seatunnel 2→1、jsonl 可解析;
   dagopt history 原 4 路径回归通过)
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

- 迁移项目有了量化进度:每周 `pipe-migrate -d legacy/ --history burndown.jsonl`,
  任务存量/L 级数量/剩余 SeaTunnel 目标一目了然,新增旧任务会被黄字点名。
- 两处 history 共用一个实现,无重复代码。
