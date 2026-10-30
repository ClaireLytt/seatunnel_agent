# 批次结果报告:数仓卫生检查 agent(lineage_hygiene)首批(2026-10-29)

## 批准依据

> 用户对候选"1. 数仓卫生检查(lineage hygiene)"所在提案回复"go on"(两次审阅成本提醒后仍继续,视为决定)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 核心:孤儿产出(ads_* 终端豁免)/死列(仅对有读者的表,分区列豁免)/悬空 DDL,基于既有 LineageGraph 与 pii 的 DDL 清单适配器 | src/seatunnel_agent/agents/data/lineage_hygiene/{analyzer,report,__init__}.py | 本批 |
| 高 | CLI `hygiene`(--dir/--sql/--file、--fail-on orphans/dead/dangling/any、-F json、-o) | src/seatunnel_agent/cli_cmds/checks.py | 本批 |
| 高 | REST `POST /api/hygiene/scan`(白名单 HYGIENE_API_ALLOWED_DIRS)+ health | lineage_hygiene/api.py | 本批 |
| 高 | MCP 工具 warehouse_hygiene(12→13;原名 lineage_hygiene 与"血缘目录工具 lineage_* 前缀"约定冲突,被既有测试拦下后改名) | mcp_toolbox/{core,ui}.py | 本批 |
| 高 | 单测 16 项(分析器 6/CLI 6/REST 3/MCP 1)+ MCP 目录期望更新 | tests/test_lineage_hygiene.py, tests/test_mcp_toolbox.py | 本批 |
| 中 | README 专节 + 命令示例 | README.md | 本批 |

## 验证结果

```
pytest tests/test_lineage_hygiene.py -q      -> 16 passed
pytest -k "hygiene or mcp" -q                -> 71 passed, 1 skipped
pytest -q                                    -> 3558 passed, 1 skipped, 250 deselected
ruff check src tests                         -> All checks passed!
mypy                                         -> Success: no issues found in 176 source files
python scripts/check_workflow.py --range origin/main...HEAD ->
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/main...HEAD)
```

## 前后差异

- 套件新增第 7 类问题的回答:「哪些可以退役」;MCP 工具 12→13;全量 pytest 3533→3558。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | Web UI 页(/hygiene)与 hub 卡、编排器路由未做 | 本批范围 | 控制批次体积 | CLI/REST/MCP 已可用 | 合入 PR #152 后作为独立批次补(与 pii React 页同模式) |
| 低 | 孤儿判定不知调度器视角(外部 BI 直读的表会被误报) | analyzer 注释 | 静态边界 | 报告定位为线索而非判决 | 文档已声明;可后续支持豁免清单 |

## 未执行的步骤

- UI 页/hub 卡(见遗留);issue #10 新候选勾选待 UI 完成后进行。
