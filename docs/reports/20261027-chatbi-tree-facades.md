# 批次结果报告:tree 三门面收口(2026-10-27)

## 批准依据

> 用户对第十二轮候选(建议"我现在做 1 收口")回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | REST `POST /metrics/tree`(零 LLM,薄壳复用 _tool_tree_attribution,支持 compare_mode) | api_metrics.py | 本批 |
| 中 | MCP `tree_attribution`(`--allow-execute` 门控,与其余分析工具同级) | mcp_server.py | 本批 |
| — | 指南 REST/MCP 清单更新 | docs/chat_bi_guide.md | 本批 |

测试:REST tree 端到端断言(mom 对比,tree 与 check_ok)并入既有端点测试;MCP e2e 断言 + execute 门控列表加入 tree_attribution。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 172 source files
python -m pytest tests/test_text2sql_metrics.py -q -> 93 passed in 12.58s
python -m pytest -q          -> 3458 passed, 1 skipped, 243 deselected in 152.71s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3458 passed(断言并入既有用例,数目持平)。
- 行为:指标树分解三门面齐平(对话/REST/MCP);引擎侧功能至此收口。

## 未解决问题 / 遗留清单

无(引擎侧)。工程/产品侧待办:PR 合并(草稿 docs/PR_DRAFT_uiskill.md)、UI 露出(建议合并后)、周报叙述(可选)。

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
