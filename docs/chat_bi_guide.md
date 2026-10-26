# Chat BI 使用指南

> 设计 PRD 见 [chat_bi_prd.md](chat_bi_prd.md)（issue #35）。
> 本文是功能与配置总览：指标语义层（含星型 JOIN）/ 归因分析（双因素+交叉
> 维度）/ 混合检索 + 值级检索 / few-shot 示例库 / 订阅推送（多渠道）/ 看板 /
> 列脱敏 / MCP / 跨模块联动 / 端到端评测。

## 快速开始

零配置试用:`seatunnel-agent chatbi-demo` 一条命令生成演示环境
(60 天带星期形态/节假日效应/退款尖峰的 sqlite 数据 + 全特性
metrics.yaml + 10 个演示问题清单),按输出提示设两个环境变量即可开问。

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
    targets: {month: 3000000}       # 可选:月/季/年目标(additive 指标)
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

口径变更追溯:`validate` 通过后自动对比 git 上一提交的 metrics.yaml,
列出口径字段级变化(expression/filters/joins/targets 等,改 display_name
不算)并点名受影响的订阅——口径改动不允许悄悄发生。

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

## 中文业务时间语义

"春节期间的 GMV""2025 国庆退款率""上季度环比"——时间短语由
`resolve_named_range` 确定性解析,所有吃 start/end 的入口(指标查询/
归因/指标树/REST/MCP)自动受益,提示词强制 LLM 原样透传、禁止自算日期:

- 相对期:今天/昨天/本周/上周/本月/上月/本季度/上季度/今年/去年/近N天
- 法定节假日(static 日历 2024–2026,国办通知原文区间):元旦/春节/清明/
  劳动节(五一)/端午/中秋/国庆(十一),支持 `2025国庆`、`春节期间` 写法;
  无年份取今天之前最近一次;未覆盖年份返回"不认识"而非猜测

## 指标树分解(北极星拆解)

指标可声明乘法因子树:

```yaml
  - name: gmv
    tree: [traffic, cvr, aov]    # gmv = 流量 × 转化率 × 客单价(因子须已定义)
```

"GMV 为什么跌"命中 `tree_attribution`:对数恒等分解
`Δln(gmv) = ΣΔln(因子) + 残差`,各因子份额 + 残差恒等于 100%(带自检;
父指标与因子乘积的度量差进残差,精确树残差≈0);份额最大的 additive
因子自动再做一层维度归因——回答从"哪个渠道"升级到"是流量跌了,主要在
app 渠道"。任一值 ≤0 或父指标无变化时显式拒绝(对数未定义)。成本
2×(1+因子数) 条 SQL + 下钻;qlog `kind=tree`。

## 指标预测

"预测下周 GMV / 未来 7 天订单量会怎样" 走 `forecast_metric` 工具，
与归因同一哲学——**数学确定性、LLM 只负责叙述**：

1. 语义层生成口径一致的**日序列 SQL**（`build_metric_series_sql`，
   纯函数，比率指标自动按天 JOIN 分子/分母）；
2. 确定性模型拟合：OLS 线性趋势 + 星期加法季节性（历史 ≥ 2 整周时启用）
   + 法定节假日/调休补班日加法偏移（`calendar_cn.py` 静态日历 2024–2026，
   历史含 ≥2 个该类日才启用，未覆盖年份自动退化），缺失日加法指标补 0、
   比率指标前向填充；
3. 输出逐期点预测 + 95% 区间（残差 σ 自检拟合质量），节假日预测行标注
   `is_holiday`；提示词强制模型以"估计值"口吻呈现，禁止自行外推数字。

参数：`horizon_days`（默认 7，上限 30，单位随粒度）、`grain`（day/week/
month，默认 day；周/月由工具层把日序列聚成 ISO 周/自然月，不完整的边缘
周期丢弃，比率指标仅支持 day）、`history_days`（day 默认 28、14–180；
week 默认 112、56–364；month 默认 365、210–900）、`end_date`（默认昨天）。
成本 1 条 SQL；审计落 qlog（`kind=forecast`）。

## 目标达成跟踪

指标声明 `targets: {month|quarter|year: 数值}` 后，"本月 GMV 达成率多少 /
照这个节奏月底能完成吗" 走 `metric_target_progress` 工具：期初至今实际值
（1 条确定性 SQL）÷ 目标 = 达成率；期末总量投影优先用预测模型（近 28 天
日序列，历史 ≥7 天），不足时退化为线性节奏外推（`projection_method` 标明
口径）。审计落 qlog（`kind=target`）。ratio 指标暂不支持 targets
（`metrics validate` 会拒绝）。

## 多指标相关性

"退款率涨是不是跟 GMV 放量有关" 走 `correlate_metrics`:两个指标的日序列
(2 条确定性 SQL)算 Pearson r,外加 ±7 天滞后扫描找最强领先/滞后关系
(`lag_days > 0` 表示 metric_a 领先)。有效对齐天数 <7 拒绝;任一侧零方差
显式标记。提示词强制模型只把 r 当关联陈述——相关≠因果,"为什么"仍引导
归因分析。审计落 qlog(`kind=correlation`)。

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

**语义缓存**:与已验证示例**完全同问**(大小写/空白/末尾标点归一后一致)
的单轮提问直接复用该 SQL,零 LLM 调用——仍走完整 execute_sql 链路
(validator/白名单/LIMIT/脱敏/qlog),执行失败自动回落 LLM 流程;改写过
的问题永不命中(改写可能改变日期/过滤,宁可多花一次 LLM)。多轮追问
不走缓存。`T2S_SEMANTIC_CACHE=0` 关闭;结果有误点 👎 即移除示例。

## 订阅推送与异动监控

三种订阅（UI 侧边栏「🔔 订阅」/ CLI `t2s-sub`）：

```bash
# 定时推数:每天 9 点推昨天的 GMV 分渠道
seatunnel-agent t2s-sub add --name GMV日报 --cron "0 9 * * *" \
    --metric gmv -d channel --webhook https://open.feishu.cn/...

# 异动监控:变动超 ±8% 才推告警,否则静默;additive 指标的告警卡自动跑归因,
# 附 Top3 贡献成员的贡献率(新增/消失成员单独标记)——告警即答案。
# 告警记忆:持续同向异常只推首日一张卡,恢复正常时推一张绿色"已恢复"卡
# (三天的事故 = 两张卡,不是三张;方向反转视为新事件)。
# 告警/恢复事件落 qlog(kind=alert/alert_recovered),metrics health 的
# "7天告警次数"由此而来。
# 告警聚合:同一调度轮内同 webhook 的多张红卡合并成"⚠ N 条告警"一张
# (告警风暴不刷屏;T2S_ALERT_AGGREGATE=0 关闭;绿卡与 run-now 不受影响)。订阅引擎的日序列有进程内 TTL 缓存
# (T2S_SERIES_CACHE_TTL,默认 600 秒,0 关闭):同指标的 digest/watch
# 晨间并发只打一次数据库。
# 比率指标(如退款率)同样支持;卡片中维度拆解标注为"各维度变化";
# 比率无定义时(分母为0/无数据)记 no_data 跳过,不发假告警
seatunnel-agent t2s-sub add --name GMV异动 --cron "30 8 * * *" \
    --metric gmv --watch --threshold 8 --watch-mode dod --webhook ...

# 模型基线异动:--watch-mode model 用预测基线(趋势+星期+节假日)代替固定阈值,
# 昨日实际落在 95% 区间外才告警——周末/节假日的天然波动不再误报;
# 历史不足 7 天记 no_data 跳过(此模式忽略 --threshold);
# 数据管道滞后(表里根本没有昨日数据)记 no_data 断更提示,不发 -100% 假告警
seatunnel-agent t2s-sub add --name GMV异动 --cron "30 8 * * *" \
    --metric gmv --watch --watch-mode model --webhook ...

# 数据新鲜度:MAX(time_column) 落后超过 --max-lag-days 才告警(每表 1 条极小 SQL;
# 比率指标自动检查分子/分母两张表)
seatunnel-agent t2s-sub add --name GMV断更 --cron "0 8 * * *" \
    --metric gmv --freshness --max-lag-days 1 --webhook ...

# 回测:上线前回放告警规则,看过去 N 天哪些天会触发(调 threshold/watch-mode 用;
# 1 条序列 SQL + 纯 Python 重放)
seatunnel-agent t2s-sub backtest <订阅ID> --days 90

# 经营日报:每指标一行 昨日值/环比/月目标达成(≤2 SQL/指标,上限 10 指标;
# --digest "" 表示全部已定义指标;单个指标查询失败只坏一行不坏整卡)
seatunnel-agent t2s-sub add --name 经营日报 --cron "0 9 * * *" \
    --digest "gmv,refund_rate,order_cnt" --webhook ...

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

订阅卡片按订阅的 `lang` 字段渲染(zh/en;digest/断更/恢复/告警全套)。

### qlog 洞察(飞轮运营)

```bash
seatunnel-agent t2s-qlog-stats --top 10
```

高频问题 × 是否已固化示例(= 语义缓存覆盖率)、失败聚类、慢查询 Top、
来源分布。把 ❌ 的高频问题 👍 固化后,下次同问即走零成本缓存。

批量固化一条命令(qlog 里本就存着每问最近一次成功的 SQL):

```bash
seatunnel-agent t2s-examples promote --top 10        # dry-run 列候选
seatunnel-agent t2s-examples promote --top 10 --yes  # 入库
```

### 资产漂移体检

```bash
seatunnel-agent t2s-doctor --ddl config/schema_ddl.sql
```

示例库(语义缓存的执行路径)/收藏/看板/订阅 对当前 DDL+指标库的静态校验:
坏表=error、可疑列=warning、订阅引用的指标/收藏缺失=error,逐条给建议;
有 error 退出码 1,可做 CI 门禁或 schema 变更后的例行检查。

### 指标健康页

```bash
seatunnel-agent metrics health --ddl config/schema_ddl.sql --ds-type sqlite --database config/demo.db
```

每指标一行:新鲜度(最新分区/滞后天数)/ 告警中(自哪天)/ 7 天查询与
失败数 / 月目标达成 / 订阅数,红黄绿排序(断更或告警中=红,有失败=黄)。

## 看板（钉选查询）

不做拖拽报表设计器；看板 = 钉选查询的有序列表。UI 侧边栏「📌 看板」：
新建看板 → 查询后点「📌 钉选最近结果」→「▶ 渲染看板」把整板结果
（表格 + 自动图表）渲染进对话流。渲染时逐项重新执行，走与交互查询相同的
validator / 白名单 / LIMIT；单项失败不影响其他项。文件
`config/t2s_boards.json`（上限 50 板 × 30 项）。

## 行级权限

列脱敏管"看什么字段",行级策略管"看哪些行"。`config/t2s_policies.yaml`
(或 `T2S_POLICIES_PATH`)定义命名策略:

```yaml
policies:
  - name: app_only
    row_filters:
      dwd.orders: "channel = 'app'"     # 条件写裸列名,注入时自动带上表别名
```

服务端设 `T2S_POLICY=app_only` 激活(**只认服务端环境,不接受客户端传入**);
执行器工厂处统一注入——对话/REST/MCP/订阅/看板/周报全链路同一个闸口,
JOIN/子查询/UNION 的每个读取点都被过滤。失败关闭:策略激活时解析不了的
SQL 直接拒绝,绝不无过滤执行;`T2S_POLICY` 指向未定义策略是硬错误。
按 API key 区分策略有赖多 key 鉴权,暂未提供。

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
`execute_readonly_sql`（仍 SELECT-only + 白名单 + LIMIT）、
`metric_attribution`、`forecast_metric`、`metric_target_progress`、
`correlate_metrics` 与 `tree_attribution`。凭据只从服务端环境读取，
不接受 MCP 参数传入。

## 查询成本预估

分区引擎上,护栏链从三层补全为四层:表白名单 → 缺分区过滤硬拦 →
**事前成本提示** → 事后慢查询/倾斜提示。能通过"有分区过滤"检查但仍会
扫宽的形态在执行前提示(`cost_hints`,只提示不拦截):

- 单边界(`pt >= '2024-01-01'` 无上界)——另一侧不受限
- 宽区间 / 宽 IN 列表(默认 >90 个分区,`T2S_COST_WARN_PARTITIONS` 可调)

需要硬约束时设 `T2S_COST_BLOCK_PARTITIONS=N`:预计扫描 ≥N 分区直接拒绝。
非日期形态的分区值不猜、不提示。

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
`GET /metrics`、以及零 LLM 确定性端点 `POST /metrics/query` /
`/metrics/attribution` / `/metrics/forecast` / `/metrics/target` /
`/metrics/correlate` / `/metrics/tree`（适合 Dify/n8n 编排；OpenAPI 见
`/docs`）。
设置 `SEATUNNEL_API_KEY` 后所有 `/api` 路由要求 `X-API-Key` 头。

> ⚠️ 安全提示:未设置 `SEATUNNEL_API_KEY` 时 API 完全开放,且订阅接口
> 接受任意 webhook URL(服务端会定时向其 POST)。凡是非单机/可信内网
> 部署,务必设置 API key,并配置 `T2S_WEBHOOK_ALLOW_HOSTS=open.feishu.cn,...`
> (域名后缀白名单,未设置则不限制;邮件渠道走服务端 SMTP 配置,不受此限)。

## 端到端评测

```bash
seatunnel-agent t2s-eval --dataset tests/fixtures/t2s_eval_demo.jsonl \
    --ds-type sqlite --database config/uitest_demo.db --limit 5
# 换模型对比: seatunnel-agent -m deepseek-chat --provider openai t2s-eval ...
```

问题 → agent（真实 LLM）→ 结果集,与 golden SQL 的结果**逐行对比**
（乱序不敏感、浮点容差、列别名无关）,输出准确率与逐题差异。

## 经营周报

```bash
seatunnel-agent t2s-report --ddl config/schema_ddl.sql --ds-type sqlite --database config/demo.db
```

确定性骨架(各指标 周值/周环比/月目标达成 + 告警中订阅 + 最大变动指标的
维度归因 Top3)落盘 `reports/t2s/weekly_<日期>.md`;配置了 LLM 时追加一段
中文摘要(提示词硬性禁止改写/估算/外推任何数字),`--no-llm` 或 LLM 不可用
时输出纯表格版——骨架本身就可读。

## 审计

每条查询落 `logs/text2sql_queries.jsonl`：`source`
(ui/api/mcp/subscription)、`metric`、生成 SQL、耗时、行数、状态。
治理侧可用 `seatunnel-agent govern --sql-dir <数仓SQL> --qlog <该文件>`
交叉出下线候选/热表/失败高发报告。
