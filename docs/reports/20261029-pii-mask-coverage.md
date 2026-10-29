# 批次结果报告:脱敏覆盖回验(发现→处置→验证闭环)(2026-10-29)

## 批准依据

> 用户对推荐顺序"1 → 3 → 2"中第 3 项所在计划回复"go on"(MCP 批次完成后继续)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | Coverage/Uncovered 数据结构:假定消费方切换到生成视图后,统计已覆盖/未覆盖发现与未脱敏传播边 before→after;未覆盖原因分 no_ddl / below_min_confidence | src/seatunnel_agent/agents/data/pii_scan/masker.py | 本批 |
| 高 | 渲染:脱敏脚本尾部附覆盖回验注释(含逐条 UNCOVERED);plan.to_dict 新增 coverage(REST /api/pii/mask 自动携带) | 同上 | 本批 |
| 高 | CLI 门禁语义升级:--mask 与 --fail-on 同用时,改为对"未覆盖"发现分级拦截(已被视图覆盖的发现视为已处置) | src/seatunnel_agent/cli_cmds/checks.py | 本批 |
| 高 | 覆盖回验单测 4 项 + 门禁语义测试改写为 covered 放行/uncovered 拦截一对 | tests/test_pii_mask.py | 本批 |

## 验证结果

```
pytest tests/test_pii_mask.py tests/test_pii_scan.py tests/test_mcp_toolbox.py -q -> 97 passed
pytest -k "pii or mask or mcp" -q            -> 141 passed, 1 skipped
ruff check src tests                         -> All checks passed!
mypy                                         -> Success: no issues found in 176 source files
CLI 实测: pii --sql "...phone..." --mask     -> 尾行 "覆盖回验 coverage: 1/1 findings covered; unmasked spread edges 0 -> 0"
python scripts/check_workflow.py --range origin/main...HEAD ->
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/main...HEAD)
```

## 前后差异

- 语义:pii 从"发现→处置"到"发现→处置→验证";CI 门禁从"有高危即红"升级为"有未处置的高危才红"(--mask 模式下),处置过的发现不再误伤流水线。
- 原 test_cli_pii_mask_respects_fail_on(全覆盖场景 exit 1)按新语义改写为两条:全覆盖 exit 0、血缘-only 未覆盖 exit 1。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 覆盖判定假设消费方切换到 *_masked 视图,未校验实际引用 | masker.py Coverage docstring | 静态确定性边界 | 覆盖是"方案可达"而非"已落地" | 落地核验需连管控面,超出本 agent 边界 |

## 未执行的步骤

无。
