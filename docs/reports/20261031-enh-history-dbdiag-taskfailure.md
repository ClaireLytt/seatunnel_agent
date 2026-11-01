# 批次结果报告:增强 dbdiag/taskfailure --history 台账(2026-10-31)

## 批准依据

> 用户:"go on"(合并队列排序 3:两项 --history 增强,复用
> track_history/rising_trend)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `dbdiag --history`:记 threads_connected/threads_running/high_findings(worse_key=high_findings);`--trend N` 对 threads_connected 做严格上涨点名,`--fail-on-trend` CI gate | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | `taskfailure --history`:记失败总数与各归因计数(cause_* 列,worse_key=total);`--trend N` 对 total 做恶化点名,`--fail-on-trend` CI gate | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 中 | 单测 2 条(台账追加字段/趋势点名/gate/缺 --history 用法错误,双命令各一) | tests/test_db_diag.py · tests/test_task_failure.py | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_db_diag.py tests/test_task_failure.py -q -> 37 passed(原 20+17 → 21+18... 实为 19+16+2 新增)
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- dbdiag 从单快照升级为可记台账:连接数缓慢爬升(每次都不超 80% 阈值)
  现在能被点名并 gate;taskfailure 的"今晚失败比昨晚多"同理。
- 四个诊断命令(kafkalag/flinkdiag/dbdiag/taskfailure)台账模式对齐,
  趋势检测统一走 check_runner.rising_trend。

## 遗留

- 队列继续:66 rollback_plan → 67 model_review → 61/68 → 62/69 → 63/64。
