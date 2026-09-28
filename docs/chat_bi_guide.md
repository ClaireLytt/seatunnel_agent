# Chat BI 使用指南

> 设计 PRD 见 [chat_bi_prd.md](chat_bi_prd.md)（issue #35）。
> 本文是功能与配置总览：指标语义层 / 归因分析 / 混合检索 / 订阅推送 /
> MCP / 跨模块联动 / 端到端评测。

## 快速开始

```bash
# 1. 定义指标口径(可选,但强烈建议——这是口径一致性的来源)
#    编辑 config/metrics.yaml,然后校验:
seatunnel-agent metrics validate --ddl config/schema_ddl.sql

# 2. 启动 Web UI,进入 /text2sql
seatunnel-agent ui            # 加 --api 同时开放 REST

# 3. 直接提问:
#    "昨天各渠道的销售额"        → 命中指标,确定性 SQL
#    "GMV 的口径是什么"          → 纯问答,不执行 SQL
#    "上周销售额为什么跌了"       → 归因分析 + 瀑布图
#    "这个数是从哪些表算出来的"    → 指标溯源(口径 + 血缘上游链)
#    贴一段 SQL 问"有没有问题"    → 静态审查(统一对话入口)
```

## 指标语义层

`config/metrics.yaml` 是"口径白名单"（`schema_ddl.sql` 是表白名单）：

```yaml
metrics:
  - name: gmv                      # 唯一 ID
    display_name: GMV
    aliases: [成交总额, 交易额]
    description: 已支付订单的应付金额合计
    table: dwd.dwd_trade_order_di  # 必须在表白名单内
    expression: SUM(pay_amount)
    time_column: dt                # 分区表必须用分区列
    dimensions: [channel, province]
    default_filters: ["order_status = 'PAID'"]
    unit: 元
    owner: 数据组
  - name: refund_rate              # 比率型:分子/分母引用加法型指标
    type: ratio
    numerator: refund_amount
    denominator: gmv
```

核心保证：命中指标的问题由 `build_metric_sql` **纯函数展开**——同样的
(指标, 维度, 时间, 过滤) 永远产出逐字节一致的 SQL，LLM 只负责"听懂问题、
选对指标"，不负责"写聚合"。

CLI：`seatunnel-agent metrics list|show <name>|validate|sql <name>`
（`validate` 出错退出码 1，可做 CI 门禁；`sql` 离线预览展开结果）。

## 归因分析

"为什么涨/跌"由确定性数学回答：两期总量对比 → 逐维度下钻 → 贡献分解
（`贡献(v) = Δv / |基期总量|`，贡献之和恒等于总变动率，带自检）。

- 对比期可由 `compare_mode` 确定性换算：`mom` 环比等长前一周期 /
  `wow` 上周同期 / `yoy` 去年同期
- 比率型指标拆分子/分母两栏；新增/消失的维度成员单独标记
- 结果自动渲染瀑布图（涨绿跌红）；`export_report` 可落盘 Markdown 报告
- 查询预算 2 + 2×维度数条 SQL；下钻达到行数上限时显式报错防静默不完整

## 混合表/指标检索

三通道融合：原关键词打分 × BM25（snake_case 拆分 + 中文 bigram，零依赖）×
可选向量。指标目录同样进入 BM25/向量索引。

| 环境变量 | 作用 |
|---|---|
| `EMBEDDING_MODEL` | 设置即启用向量通道（OpenAI 兼容 `/embeddings`） |
| `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` | 端点与密钥（缺省回落 LLM 配置） |
| `T2S_RETRIEVAL_WEIGHTS` | 三通道权重，默认 `0.4,0.3,0.3` |
| `T2S_SCHEMA_PROMPT_LIMIT` | 超过该表数提示词只注入表名（默认 50） |

回归门禁：`seatunnel-agent t2s-bench --ddl tests/fixtures/t2s_bench_schema.sql
--bench tests/fixtures/t2s_retrieval_bench.jsonl --gate`（hybrid 不得低于
keyword-only）。配置好 embedding 后重跑同一命令即可量化向量通道收益。

## 订阅推送与异动监控

三种订阅（UI 侧边栏「🔔 订阅」/ CLI `t2s-sub`）：

```bash
# 定时推数:每天 9 点推昨天的 GMV 分渠道
seatunnel-agent t2s-sub add --name GMV日报 --cron "0 9 * * *" \
    --metric gmv -d channel --webhook https://open.feishu.cn/...

# 异动监控:变动超 ±8% 才推告警(含 Top3 贡献成员),否则静默
seatunnel-agent t2s-sub add --name GMV异动 --cron "30 8 * * *" \
    --metric gmv --watch --threshold 8 --watch-mode dod --webhook ...

# 收藏推数:参数化收藏 + 日期宏(${yesterday}/${today_pt}/${month_start}...)
seatunnel-agent t2s-sub add --name 周报 --cron "0 10 * * 0" --favorite <id> ...

# 调度:随 Web UI 自动拉起;无 UI 部署用常驻进程
seatunnel-agent t2s-cron --serve
```

安全边界：连接服务端解析（加密预设/环境变量，凭据不入订阅文件）；执行走
validator + 表白名单 + 强制 LIMIT；失败推红卡（静默≠成功）。配置
`FEISHU_APP_ID`/`FEISHU_APP_SECRET` 后成功卡片自动内嵌图表。

## MCP Server（IDE 内取数）

```bash
seatunnel-agent t2s-mcp --ds-type sqlite --database config/demo.db --allow-execute
```

注册到 Claude Code / Claude Desktop / Cline 后可用的工具：
`list_tables` / `get_table_schema` / `match_tables`（混合检索）/
`match_metrics` / `explain_metric` / `metric_sql`（确定性展开）/
`trace_metric`（溯源）。`--allow-execute` 才开放
`execute_readonly_sql`（仍 SELECT-only + 白名单 + LIMIT）与
`metric_attribution`。凭据只从服务端环境读取，不接受 MCP 参数传入。

## 跨模块联动

- **execute_sql × SQL Review**：每条执行的 SQL 先过静态 linter，
  critical/risk 附在 `review_findings`（只提示不拦截）
- **execute_sql × 数据倾斜**：批处理引擎慢查询（`T2S_SLOW_QUERY_MS`，
  默认 5000ms）附 `skew_hints`
- **trace_metric × 血缘**：`T2S_LINEAGE_SQL_DIR` 指向数仓 SQL 目录后，
  溯源附每张来源表的上游加工链
- **统一对话入口**：对话里直接贴 SQL——`review_sql`（审查）/
  `skew_check`（倾斜）/ `transpile_sql`（方言翻译），零执行

## REST API 与鉴权

`seatunnel-agent ui --api` 开放 `/api/text2sql/`：`POST /query`（NL 问答）、
`GET /metrics`、`POST /metrics/query` 与 `POST /metrics/attribution`
（零 LLM 确定性端点，适合 Dify/n8n 编排；OpenAPI 见 `/docs`）。
设置 `SEATUNNEL_API_KEY` 后所有 `/api` 路由要求 `X-API-Key` 头。

## 端到端评测

```bash
seatunnel-agent t2s-eval --dataset tests/fixtures/t2s_eval_demo.jsonl \
    --ds-type sqlite --database config/uitest_demo.db --limit 5
# 换模型对比: seatunnel-agent -m deepseek-chat --provider openai t2s-eval ...
```

问题 → agent（真实 LLM）→ 结果集,与 golden SQL 的结果**逐行对比**
（乱序不敏感、浮点容差、列别名无关）,输出准确率与逐题差异。

## 审计

每条查询落 `logs/text2sql_queries.jsonl`：`source`
(ui/api/mcp/subscription)、`metric`、生成 SQL、耗时、行数、状态。
治理侧可用 `seatunnel-agent govern --sql-dir <数仓SQL> --qlog <该文件>`
交叉出下线候选/热表/失败高发报告。
