# 批次结果报告:Agent 65 源目 Schema 对齐 schema_align(2026-10-31)

## 批准依据

> 用户:"go on"(合并队列排序 2:65 schema_align — SeaTunnel 同步场景
> 契合度最高;与 schema_drift/config_diff 查重边界已在提案说明)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性对齐核心:双 DDL 解析(括号配平,DECIMAL(38,6) 不碎;MySQL/Hive/Doris 写法通吃,含 NOT NULL/DEFAULT 捕获),按列名匹配后判定 SA001 目标缺列(键列高)/SA002 无默认 NOT NULL 多列/SA003 收窄(int 位宽、decimal 精度、varchar 长度、浮点→整数)/SA004 string→数值时间危险转换/SA005 时间截断/SA006 可空→NOT NULL;放宽静默通过 | src/seatunnel_agent/agents/data/schema_align/aligner.py | 本批 |
| 高 | zh/en 报告(每条附处方)+ i18n + LLM 对齐评审(opt-in) | schema_align/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router)+ MCP 工具 + manifest(build 组,order 88) | schema_align/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent schemaalign`(-s/--sink/--fail-on-high) | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | React 页(useRunner,双 DDL 输入,demo 预填) | frontend/schema_align/* + workspace 注册 | 本批 |
| 中 | 示例源目 DDL 对 + 单测 18 条 + 页面回归 2 条 | examples/schemaalign_demo/* · tests/test_schema_align.py · tests/test_schemaalign_page.py | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_schema_align.py -q      -> 18 passed
python -m pytest -m uitest tests/test_schemaalign_page.py -q -> 2 passed
python -m pytest tests/test_schema_align.py tests/test_metric_attribution.py tests/test_hub_pages.py tests/test_mcp_toolbox.py -q -> 83 passed
seatunnel-agent schemaalign -s source.sql --sink sink.sql -> 7 条发现六类全中(缺列/NOT NULL 陷阱/收窄×3/时间截断/可空反转)
npm run build (frontend/schema_align)               -> built in 3.00s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:build 组新增 /schemaalign 卡片,REST/MCP/CLI/React 四入口
  齐备;同步作业上线前的源目两端体检此前无覆盖(schema_drift 管单表
  时间漂移)。
- 测试:新增 18 条单测 + 2 条页面回归,全部通过;相关套件 83 passed 无回归。

## 遗留

- 队列继续:增强(dbdiag/taskfailure --history)→ 66 rollback_plan →
  67 model_review → 61/68 → 62/69 → 63/64。
