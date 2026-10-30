# 批次结果报告:check-runner(2026-10-29)

## 批准依据

> 用户在架构评审报告(候选 1-4)后批示:"全部完成"。本批次为候选 1:check 形状的 CLI 命令收敛为 CheckSpec + run_check。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 新增 check_runner:CheckSpec + analyze_input / emit_report / save_output / fail_check / severity_gate / run_check | src/seatunnel_agent/cli_cmds/check_runner.py | 本批次 |
| 高 | pii 命令收敛:标准路径走 spec,--mask 分支保留为命令自身逻辑(含治理后 gate) | src/seatunnel_agent/cli_cmds/checks.py | 本批次 |
| 高 | hygiene 命令收敛为 run_check(exempt YAML 解析与 counts gate 留在命令内) | src/seatunnel_agent/cli_cmds/checks.py | 本批次 |
| 高 | metaquality 命令收敛为 run_check(severity gate) | src/seatunnel_agent/cli_cmds/checks.py | 本批次 |

## 验证结果

```
python -m pytest tests/test_pii_scan.py tests/test_pii_mask.py tests/test_lineage_hygiene.py tests/test_metadata_quality.py -q
  -> 96 passed in 4.78s
python -m pytest -q  -> 3572 passed, 1 skipped, 259 deselected in 154.96s
ruff check src tests -> All checks passed!
mypy                 -> Success: no issues found in 176 source files
```

```
check_workflow 输出(提交后运行):
[PASS] AI 署名: 无 AI 署名(范围 origin/pso..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘
[PASS] 报告含验证输出
[PASS] floor: 无作弊变绿改动(范围 origin/pso..HEAD)
```

无 UI 改动。

## 前后差异

- 行为不变:各命令的 UsageError 文案、错误标签(扫描失败/分析失败/检查失败)、json/stderr 的 gate 输出、历史记录时机(输出后、gate 前)逐一保留;全量 3572 测试前后均通过。
- 代码形状:checks.py 1150 → 1098 行,三个命令体的分析/输出/落盘/gate 样板收敛到一个深模块;新增 agent 的 check 命令只需声明一个 CheckSpec。
- pii 的 --mask 分支与 treatment-aware gate、hygiene 的 counts gate 属各命令自身语义,显式保留在命令内,不塞进 seam。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- 候选 3(manifest 能力注册)在下一批次继续。
