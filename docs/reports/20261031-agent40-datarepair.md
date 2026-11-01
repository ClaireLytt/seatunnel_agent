# 批次结果报告:Agent 40 一致性修复 data_repair(2026-10-31)

## 批准依据

> 用户:"适配以上的agent 制定好方案后一步步执行"(36–47 清单)。
> docs/data_agents_36_47_plan.md 里程碑 6:40 data_repair(消费 36/37
> 形状的发现,套件一收口)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性规划核心:复用 dup_check 检测 + sample_profile 剖析,生成修复动作 — ROW_NUMBER 去重(全行/主键/业务键三层)、COALESCE 空值回填、TRIM/LOWER 标准化、千分位/货币清洗转数值、离群格式改写;<尖括号> 占位符留人工决策 | src/seatunnel_agent/agents/data/data_repair/planner.py | 本批 |
| 高 | zh/en 报告(动作表 + SQL 代码块)+ i18n + LLM 变更说明(opt-in) | data_repair/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router)+ MCP 工具 + manifest | data_repair/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent datarepair`(-t/--pk/--biz-key/--llm) | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | React 页(useRunner,表名/键输入,demo 预填) | frontend/data_repair/* + workspace 注册 | 本批 |
| 中 | 示例数据 + 单测 16 条 + 页面回归 2 条 | examples/datarepair_demo/events.csv · tests/test_data_repair.py · tests/test_datarepair_page.py | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_data_repair.py -q       -> 16 passed
python -m pytest -m uitest tests/test_datarepair_page.py -q -> 2 passed
python -m pytest tests/test_data_repair.py tests/test_quality_trace.py tests/test_data_volatility.py tests/test_dup_check.py tests/test_dist_anomaly.py tests/test_sample_profile.py tests/test_hub_pages.py tests/test_mcp_toolbox.py -q -> 163 passed
seatunnel-agent datarepair -f events.csv -t dwd.pay_events --pk event_id -> 2 条去重动作(row/pk),SQL 模板含 PARTITION BY event_id
npm run build (frontend/data_repair)                -> built in 2.92s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:quality 组新增 /datarepair 卡片,REST/MCP/CLI/React 四入口
  齐备;套件一(36/37/38/39/40/41)六个 agent 全部落地,互相衔接:
  41 profiler → 36 漂移对比与 40 修复共用;37 检测 → 40 去重动作;
  39 处方 → 38 根因追踪。
- 测试:新增 16 条单测 + 2 条页面回归,全部通过;套件一相关 163 passed。

## 遗留

- 套件二(42–47 资产治理)继续按 docs/data_agents_36_47_plan.md 落地。
