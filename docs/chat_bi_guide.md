# Chat BI 使用指南

> 设计 PRD 见 [chat_bi_prd.md](chat_bi_prd.md)（issue #35）。
> 本文是功能与配置总览：指标语义层（含星型 JOIN）/ 归因分析（双因素+交叉
> 维度）/ 混合检索 + 值级检索 / few-shot 示例库 / 订阅推送（多渠道）/ 看板 /
> 列脱敏 / MCP / 跨模块联动 / 端到端评测。

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

### 星型 JOIN（维表维度）

真实数仓的维度值常在维表里（`channel_id` → `dim_channel.channel_name`）。
additive 指标可声明 `joins`，把维表列作为下钻维度：

```yaml
  - name: gmv
    table: dwd.dwd_trade_order_di      # 事实表(度量/过滤只能引用它的列)
    expression: SUM(pay_amount)
    time_column: dt
    joins:
      - table: dim.dim_channel         # 必须在表白名单内,且是非分区表
        alias: ch                      # 唯一别名(t 是事实表保留别名)
        local_key: channel_id          # 事实表侧关联列
        remote_key: channel_id         # 维表侧(缺省同 local_key)
        type: left                     # left | inner
        filters: ["is_deleted = 0"]    # 附加在 ON 上的维表过滤
    dimensions: [channel_id, ch.channel_name]   # 维表维度写 别名.列名
```

展开仍是纯函数：事实表列自动加 `t.` 前缀，维表维度按 `别名.列名` 限定，
结果列保持裸名（比率外层查询与归因下钻对别名透明）。边界：join 表必须
非分区（分区维表先物化为快照）；度量表达式与 default_filters 只能引用
事实表列。

## 归因分析

"为什么涨/跌"由确定性数学回答：两期总量对比 → 逐维度下钻 → 贡献分解
（`贡献(v) = Δv / |基期总量|`，贡献之和恒等于总变动率，带自检）。

- 对比期可由 `compare_mode` 确定性换算：`mom` 环比等长前一周期 /
  `wow` 上周同期 / `yoy` 去年同期
- 比率型指标除分子/分母两栏外，还输出**精确双因素分解** `factor_split`：
  `ΔR = ΔN/D_当期 + (N_基期/D_当期 - N_基期/D_基期)`，两效应之和恒等于
  比率变动（代数恒等式，带自检）
- `cross=true` / `cross_dimensions=[d1,d2]` 追加**交叉维度下钻**（哪个渠道
  的哪个省份，+2 条 SQL，贡献恒等式对交叉分组同样成立）
- 新增/消失的维度成员单独标记
- 结果自动渲染瀑布图（涨绿跌红）；`export_report` 可落盘 Markdown 报告
- 查询预算 2 + 2×维度数条 SQL；下钻达到行数上限时显式报错防静默不完整

## 指标预测

"预测下周 GMV / 未来 7 天订单量会怎样" 走 `forecast_metric` 工具，
与归因同一哲学——**数学确定性、LLM 只负责叙述**：

1. 语义层生成口径一致的**日序列 SQL**（`build_metric_series_sql`，
   纯函数，比率指标自动按天 JOIN 分子/分母）；
2. 确定性模型拟合：OLS 线性趋势 + 星期加法季节性（历史 ≥ 2 整周时启用），
   缺失日加法指标补 0、比率指标前向填充；
3. 输出逐日点预测 + 95% 区间（残差 σ 自检拟合质量），提示词强制模型
   以"估计值"口吻呈现，禁止自行外推数字。

参数：`horizon_days`（默认 7，上限 30）、`history_days`（默认 28，
14–180）、`end_date`（默认昨天）。成本 1 条 SQL；审计落 qlog
（`kind=forecast`）。

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
keyword-only，已接入 tests.yml CI）。配置好 embedding 后重跑同一命令即可
量化向量通道收益。

### 值级检索（单元格取值 → 表/列/字面量）

"华东地区的销售额" 里的 **华东** 不在任何表名/列名里——值级索引采样低基数
字符串列的枚举值（≤50 值/列、≤10 列/表、跳过分区表防全表扫描），命中后
`match_tables` 附带 `value_hits`（表/列/字面量），LLM 把取值**原样**写进
WHERE，杜绝字面量拼错。

```bash
seatunnel-agent t2s-index-values --ds-type sqlite --database config/demo.db
# 或 --connection <已保存连接名>；索引落 logs/.t2s_index/<schema_hash>.values.json
```

sqlite 会话首次使用自动构建；其他引擎 `T2S_VALUE_INDEX=1` 开启自动构建，
`=0` 全局关闭。

## few-shot 示例库（准确率飞轮）

已验证的 (问题, SQL) 对是提升 Text2SQL 准确率最有效的上下文。两个来源：

- **UI 反馈**：查询结果旁点 **👍 结果正确** → (问题, 最终 SQL) 自动存为
  验证示例；**👎 结果有误** → 移除同问题示例并落 qlog 审计
- **手工维护**：`seatunnel-agent t2s-examples add -q "问题" -s "SQL"`
  （`list` / `rm <id>`；文件 `config/t2s_examples.json` 可直接编辑）

检索用 BM25（与表检索同分词），Top-3 命中注入**用户消息**（非系统提示词，
逐问题自适应）；无命中时行为与之前完全一致。

## 订阅推送与异动监控

三种订阅（UI 侧边栏「🔔 订阅」/ CLI `t2s-sub`）：

```bash
# 定时推数:每天 9 点推昨天的 GMV 分渠道
seatunnel-agent t2s-sub add --name GMV日报 --cron "0 9 * * *" \
    --metric gmv -d channel --webhook https://open.feishu.cn/...

# 异动监控:变动超 ±8% 才推告警(含 Top3 贡献成员),否则静默
# 比率指标(如退款率)同样支持;卡片中维度拆解标注为"各维度变化";
# 比率无定义时(分母为0/无数据)记 no_data 跳过,不发假告警
seatunnel-agent t2s-sub add --name GMV异动 --cron "30 8 * * *" \
    --metric gmv --watch --threshold 8 --watch-mode dod --webhook ...

# 收藏推数:参数化收藏 + 日期宏(${yesterday}/${today_pt}/${month_start}...)
seatunnel-agent t2s-sub add --name 周报 --cron "0 10 * * 0" --favorite <id> ...

# 调度:随 Web UI 自动拉起;无 UI 部署用常驻进程
seatunnel-agent t2s-cron --serve
```

**多渠道推送**：target URL 自动识别渠道——飞书（缺省）/ 钉钉
（`oapi.dingtalk.com`）/ 企业微信（`qyapi.weixin.qq.com`）/ 邮件
（`mailto:addr`，SMTP_HOST/PORT/USER/PASS 配置，默认 STARTTLS）。订阅
schema 不变，换个 URL 即换渠道。

安全边界：连接服务端解析（加密预设/环境变量，凭据不入订阅文件）；执行走
validator + 表白名单 + 强制 LIMIT；失败推红卡（静默≠成功）。配置
`FEISHU_APP_ID`/`FEISHU_APP_SECRET` 后飞书成功卡片自动内嵌图表。

## 看板（钉选查询）

不做拖拽报表设计器；看板 = 钉选查询的有序列表。UI 侧边栏「📌 看板」：
新建看板 → 查询后点「📌 钉选最近结果」→「▶ 渲染看板」把整板结果
（表格 + 自动图表）渲染进对话流。渲染时逐项重新执行，走与交互查询相同的
validator / 白名单 / LIMIT；单项失败不影响其他项。文件
`config/t2s_boards.json`（上限 50 板 × 30 项）。

## 列脱敏

敏感结果列（手机号/身份证/邮箱/银行卡，按结果列名含别名识别）在
**呈现边缘**统一脱敏：execute_sql 预览、CSV/Excel/PDF 导出、订阅卡片、
看板渲染。引擎内部保持原值（归因/对比/图表数学不受影响）。默认开启，
`T2S_MASKING=0` 关闭，`T2S_MASK_COLUMNS=a,b` 追加自定义列名。手机
`138****78`、身份证 `1101***********234`、邮箱 `a***@example.com`。

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
