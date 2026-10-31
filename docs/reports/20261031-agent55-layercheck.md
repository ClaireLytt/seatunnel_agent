# 批次结果报告:Agent 55 数仓分层体检 layer_check(2026-10-31)

## 批准依据

> 用户:"think about new functions"后"go on"(55–59 候选套件,排序 55
> 先行:复用血缘、规则价值最高;与 metadata_quality/sql_review 查重
> 边界已在提案说明)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性检查核心:复用 quality_trace.build_graph_from_sql(即 data_lineage 解析器),命名前缀定层(内置 ods/stg=0、dwd/dim=1、dws/dwm=2、ads/rpt/app=3,tmp 忽略;parse_layer_map 自定义替换),逐边判定 LC001 跨层(跳 2+ 层,跳 3 层为高)/LC002 反向依赖(必高)/LC003 同层叠加(聚合层)/LC004 未知分层 | src/seatunnel_agent/agents/data/layer_check/checker.py | 本批 |
| 高 | zh/en 报告(违规表 + 整改处方)+ i18n + LLM 整改通报(opt-in) | layer_check/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router,layers_text 自定义分层)+ MCP 工具 + manifest(governance 组,order 82) | layer_check/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent layercheck`(--layers 文件/--fail-on-high) | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | React 页(useRunner,SQL+自定义分层输入,demo 预填) | frontend/layer_check/* + workspace 注册 | 本批 |
| 中 | 示例流水线 + 单测 19 条 + 页面回归 2 条 | examples/layercheck_demo/pipeline.sql · tests/test_layer_check.py · tests/test_layercheck_page.py | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_layer_check.py -q       -> 19 passed
python -m pytest -m uitest tests/test_layercheck_page.py -q -> 2 passed
python -m pytest tests/test_layer_check.py tests/test_quality_trace.py tests/test_hub_pages.py tests/test_mcp_toolbox.py -q -> 85 passed
seatunnel-agent layercheck -f pipeline.sql -> LC001 高(ods→ads 跳 2 层)/LC002 高(dwd 读 dws)/LC003 低(ads 叠 ads)全中
npm run build (frontend/layer_check)                -> built in 2.95s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:governance 组新增 /layercheck 卡片,REST/MCP/CLI/React
  四入口齐备;分层拓扑规则此前无 agent 覆盖(metadata_quality 管声明、
  sql_review 管写法)。血缘解析零重写。
- 测试:新增 19 条单测 + 2 条页面回归,全部通过;相关套件 85 passed 无回归。

## 遗留

- 候选排序继续:56 partition_health → 57 capacity_forecast →
  58 config_diff → 59 alert_storm → 增强(dbdiag/taskfailure --history)。
