# 批次结果报告:skew-runtime-flink(2026-10-28)

## 批准依据

> 用户:"go on"(对「批次 1 改做 Flink 引擎运行时诊断,Zeta 因无 per-task 指标暂缓」调整方案的批准)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `analyze_flink(base_url, job_id, fetch)`:Flink REST 作业详情 → 按 read-bytes 取最重 vertex → 逐 vertex 拉 subtasks,per-subtask duration/read-bytes 套用既有 max/median 判定;label=`jobName (jobId)` | agents/data/data_skew/runtime.py | 本批次 |
| 高 | 三门面:CLI `skew-runtime --flink <url> --app <jobId>`(三选一互斥校验,--fail 生效);REST `POST /api/skew/runtime/flink`;MCP `skew_runtime_flink`(含 no-db 档) | cli_cmds/skew.py, data_skew/api.py, mcp_server.py | 本批次 |
| 中 | /mcp 页描述、MCP instructions、指南(CLI 示例 + MCP 表 + Zeta 暂不支持说明) | mcp_toolbox/ui.py, docs/data_skew_guide.md | 本批次 |
| 高 | 测试:fake-fetch 解析(拖尾 confirmed/错误三径)、CLI(含 --fail、互斥用法)、REST 端点、工具集合断言更新 | tests/test_data_skew.py, tests/test_mcp_toolbox.py | 本批次 |

**证据先行**:Zeta 不可行与 Flink 可行均经官方文档核实——Zeta REST 仅作业级聚合与按表汇总(rest-api-v2);Flink `GET /jobs/:id/vertices/:vid` 的 subtasks 带 per-subtask duration 与 IOMetricsInfo(read-records/read-bytes)。

## 验证结果

```
ruff check src tests                 -> All checks passed!
mypy                                 -> Success: no issues found in 175 source files
pytest tests/test_data_skew.py tests/test_mcp_toolbox.py -q -> 236 passed
pytest -q(全量)                     -> 3509 passed, 1 skipped, 248 deselected, 2 warnings in 145.68s
python scripts/check_workflow.py     -> 提交后全 [PASS](见对话)
```

无 UI 代码改动,未跑 uitest。

## 前后差异

- 测试类:全量 3506 → 3509 passed(+3:fake-fetch / CLI / REST)。
- 行为:运行时诊断此前仅 Spark(event log / History Server);现在 SeaTunnel on Flink 的作业可直接按 per-subtask 指标定位拖尾 vertex,复测对比(diagnose_and_log)自动生效。Zeta 暂不支持并在指南中说明原因。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | Zeta 引擎运行时诊断缺失 | Zeta rest-api-v2 无 per-task 指标(官方文档) | 引擎能力限制,非本仓可解 | Zeta 作业只能靠 splitkey/静态线 | 跟踪上游;引擎暴露 per-task 指标后按 analyze_flink 同型接入 |
| 低 | 前端 Runtime 面板未加 Flink 入口(REST 已就绪) | frontend/data_skew RuntimePanel 仅 eventlog/History Server | 控制批次范围 | 页面用户暂用 CLI/MCP | 用户圈选后加(UI 批次含 uitest) |

## 未执行的步骤

- uitest:无 UI 改动,不要求。
