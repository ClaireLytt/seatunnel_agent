# 批次结果报告:Agent 46 数据库运行诊断 db_diag(2026-10-31)

## 批准依据

> 用户:"适配以上的agent 制定好方案后一步步执行"(36–47 清单)。
> docs/data_agents_36_47_plan.md 里程碑 11:46 db_diag(文本形输入,
> 连库实测留给 mcp_toolbox 既有通道)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性诊断核心:状态快照 JSON(各节可选)→ DB001–DB006 规则 — 连接池 80/95%、执行线程 32/128、锁等待 5/30s(附最严重阻塞对)、死锁(列表或计数)、慢查询 >1s 热点、CPU 80/95%,每条附处方 | src/seatunnel_agent/agents/data/db_diag/diagnoser.py | 本批 |
| 高 | zh/en 报告(处方指向 slowquery/index-adv)+ i18n + LLM 事故通报(opt-in) | db_diag/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router)+ MCP 工具 + manifest(governance 组) | db_diag/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent dbdiag`(--llm/--fail-on-high) | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | React 页(useRunner,demo 预填) | frontend/db_diag/* + workspace 注册 | 本批 |
| 中 | 示例快照 + 单测 19 条 + 页面回归 2 条 | examples/dbdiag_demo/snapshot.json · tests/test_db_diag.py · tests/test_dbdiag_page.py | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_db_diag.py -q           -> 19 passed
python -m pytest -m uitest tests/test_dbdiag_page.py -q -> 2 passed
python -m pytest tests/test_db_diag.py tests/test_storage_cost.py tests/test_hub_pages.py tests/test_mcp_toolbox.py -q -> 84 passed
seatunnel-agent dbdiag -f snapshot.json -> 6 条发现(DB001/003/004/005 高 + DB002/006),处方正确指向 slowquery/index-adv
npm run build (frontend/db_diag)                    -> built in 2.98s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:governance 组新增 /dbdiag 卡片,REST/MCP/CLI/React 四入口
  齐备;与 mcp_toolbox 分工明确(文本快照诊断 vs 连库实测)。
- 测试:新增 19 条单测 + 2 条页面回归,全部通过;相关套件 84 passed 无回归。

## 遗留

- 里程碑 12(47 grant_review,套件二收口)继续落地。
