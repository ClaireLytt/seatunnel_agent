# PRD · Chat BI 演进：指标语义层 × 归因分析 × RAG 检索 × 订阅推送 × MCP

> Issue: https://github.com/ClaireLytt/seatunnel_agent/issues/35
> 状态: v1 已实现 (2026-09-28) — M1 语义层 / M2 归因 / M3 混合检索+bench / M4 订阅+MCP 全部完成
> 前置: Text2SQL 模块（复用其 agent 循环 / SchemaStore / validator / executor / chart / qlog）

## 1. 背景与目标

现有 Text2SQL 是一个"单次取数工具"：问题 → 猜表 → LLM 现场写 SQL → 执行。
它有三个结构性短板，决定了它还不是 "BI"：

1. **口径不一致**：同一个"GMV"两次提问，LLM 可能选不同表、写不同聚合，
   算出两个数。业务指标的计算口径完全依赖 LLM 现场发挥。
2. **只会"查数"，不会"分析"**："上周 GMV 为什么跌了" 这类问题只能返回
   一条查询，无法自动下钻、分解贡献、产出结论。
3. **表多了就不准**：`matcher.py` 的关键词 + CJK n-gram 打分在几十张表内
   够用，几百张表时命中率和提示词长度都会失控（context rot）。

本期把 Chat BI 从"取数工具"升级为"分析平台"，共五个能力，按依赖排序：

| 阶段 | 能力 | 一句话 |
|------|------|--------|
| P1 | 指标语义层 | 指标口径集中定义，NL 命中指标后**确定性展开** SQL |
| P2 | 归因分析 Agent | 异动检测 → 维度下钻 → 贡献分解 → 分析报告 |
| P3 | RAG 混合检索 | 向量/BM25 × 现有关键词打分，支撑大规模 schema |
| P4 | 订阅推送 | 收藏查询 + 定时执行 + 飞书卡片，"数找人" |
| P5 | Text2SQL MCP | 对话式取数暴露给 Claude Code / Cursor 等外部 agent |

**非目标（Out of Scope）**：
- 不做多租户 / 用户权限体系（单机工具定位不变）
- 不做拖拽式报表设计器（图表继续走 `chart.py` 自动推断）
- 不替换现有 matcher —— RAG 是混合加权，关键词打分保留为保底与平票裁决
- 归因 v1 只做**加法型指标**的贡献分解；比率型指标输出分子/分母各自变动，不做双因素分解
- 订阅推送 v1 只支持飞书 webhook（企微/钉钉留扩展点）

## 2. 用户与场景

| 场景 | 输入 | 输出 |
|------|------|------|
| S1 口径一致取数 | "昨天各渠道的 GMV" | 命中指标 `gmv` → 确定性 SQL → 结果 + 图表 |
| S2 指标口径咨询 | "GMV 的口径是什么？和销售额什么区别" | 纯问答（不执行 SQL）：口径说明、计算公式、负责人 |
| S3 异动归因 | "上周 GMV 环比为什么跌了" | 归因报告：总变动、Top 贡献维度值、瀑布图、LLM 解读 |
| S4 大规模库表取数 | 800 张表的 DDL + 任意问题 | 混合检索 Top-K 进提示词，命中率不随表数下降 |
| S5 定时订阅 | 收藏"每日 GMV 日报" + cron | 每天 9 点飞书卡片推送结果表格 + 环比 |
| S6 IDE 内取数 | Claude Code 里问"查下昨天订单量" | MCP 工具链完成匹配→SQL→执行，结果返回 IDE |

## 3. P1 指标语义层（Semantic Layer）

### 3.1 指标定义文件

新增 `config/metrics.yaml`（路径可由 UI/CLI 覆盖），与 `schema_ddl.sql`
同级——DDL 是"表的白名单"，metrics.yaml 是"口径的白名单"：

```yaml
version: 1
metrics:
  - name: gmv                      # 唯一 ID（英文蛇形）
    display_name: GMV              # 展示名
    aliases: [成交总额, 交易额, gmv]  # NL 匹配别名
    description: 已支付订单的应付金额合计，含运费，不含退款冲销
    table: dwd.dwd_trade_order_di  # 必须存在于 SchemaStore（复用表白名单）
    expression: SUM(pay_amount)    # 聚合表达式（列必须存在于该表）
    time_column: dt                # 时间/分区列
    dimensions: [channel, province, category_id]   # 允许下钻的维度列
    default_filters: ["order_status = 'PAID'"]     # 恒定口径过滤
    unit: 元
    owner: 数据组-张三
  - name: refund_rate              # 派生指标：两个基础指标之比
    display_name: 退款率
    aliases: [退款占比]
    type: ratio                    # 缺省 additive（加法型）
    numerator: refund_amount       # 引用其他 metric 的 name
    denominator: gmv
    unit: '%'
```

### 3.2 模块

```
src/seatunnel_agent/text2sql/metrics.py
  MetricDef / MetricStore (dataclass + YAML 解析，风格对齐 schema.py)
  MetricStore.load(path, schema_store)   # 加载即校验：表在白名单、列存在、
                                         # 维度列存在、派生指标引用闭环检测
  MetricStore.match(question) -> list[(MetricDef, score)]
                                         # 复用 matcher 的分词/别名打分
  build_metric_sql(metric, dims, time_range, extra_filters, ds_type)
      -> str                             # 确定性 SQL 生成（见 3.3）
```

### 3.3 确定性 SQL 展开（口径一致性的核心）

`build_metric_sql` 是**纯函数**：同一 (指标, 维度, 时间范围, 过滤) 输入
永远产出同一条 SQL——不经过 LLM。生成规则：

1. `SELECT {dims}, {expression} AS {name} FROM {table}`
2. WHERE = 时间列范围（复用 `partition.py` 的时间解析与分区裁剪）
   ∧ `default_filters` ∧ 用户附加过滤
3. 维度只允许 `dimensions` 白名单内的列；越界直接报错，不静默忽略
4. ratio 指标：两个子查询按维度 LEFT JOIN，分母 0 保护（`NULLIF`）
5. 产出的 SQL 仍然全量通过 `validator.validate_sql`（双保险）

### 3.4 Agent 集成

`tools.py` 新增两个工具（现有 6 个不动）：

- **match_metrics(question)**：返回命中的指标及口径摘要。系统提示词新增
  硬规则：*问题涉及业务指标时必须先调 match_metrics；命中即用
  build_metric_sql 展开，禁止手写聚合*——这是口径一致性的提示词侧约束。
- **build_metric_sql(metric, dimensions, time_range, filters)**：包装 3.3
  的纯函数，返回 SQL 字符串，由 LLM 决定是否接 execute_sql。

`prompts.py` 的 schema 摘要区追加"指标目录"段（name/display/口径一行一条），
无 metrics.yaml 时该段为空，**行为与现状完全一致**（向后兼容）。

S2 场景（口径咨询）无需新工具：match_metrics 返回的口径详情足够 LLM 直接
作答，系统提示词注明"咨询口径时不要执行 SQL"。

### 3.5 界面 / CLI / REST

- UI（/text2sql 页）：左侧新增"指标目录"折叠面板——搜索框 + 指标卡
  （展示名/口径/owner/单位），点击卡片填充"查询 {display_name} 按 {dim}"
  到输入框（复用现有 hint-card 机制）
- CLI：`seatunnel-agent metrics list|show <name>|validate`（validate 供 CI
  校验 metrics.yaml 与 DDL 的一致性）
- REST：`GET /api/text2sql/metrics`（目录）、
  `POST /api/text2sql/metrics/query`（结构化参数直接查指标，不走 LLM——
  给 Dify/n8n 等编排工具用的确定性端点）

## 4. P2 归因分析 Agent

### 4.1 归因模型（全部确定性计算，LLM 只做最后解读）

```
src/seatunnel_agent/text2sql/attribution.py
  run_attribution(metric, dim, curr_range, prev_range, runtime) -> AttributionResult
```

对加法型指标：

1. 总量对比：`build_metric_sql(metric, [], curr)` 与 prev 各执行一次
   → 总变动 Δ 与变动率
2. 维度下钻：`build_metric_sql(metric, [dim], curr/prev)` 各一次，
   按维度值对齐（复用 `differ.py` 的对齐逻辑）
3. 贡献度：`contribution(v) = (curr_v - prev_v) / |prev_total|`，
   贡献合计恒等于总变动率（可自检）；新增/消失的维度值单独列出
4. 多维度：对 metric.dimensions 中每个维度重复 2-3，按"头部集中度"
   （Top3 贡献绝对值之和）排序，选出最能解释变动的维度

比率型指标：分别对分子、分母跑上述流程，报告呈现"分子变动 × 分母变动"
两栏，不做乘法分解（v1 边界，报告中明示）。

### 4.2 Agent 集成与报告

- 新工具 **run_attribution(metric, curr_range, prev_range, dimension?)**：
  省略 dimension 时自动遍历所有允许维度并挑选最优
- 报告 = 确定性事实区（总变动、各维度贡献表、瀑布数据）+ LLM 解读区
  （明确标注"以下为模型解读"），风格对齐 sql_review 的固定格式报告
- `chart.py` 新增瀑布图（waterfall）类型，归因结果自动出图
- 查询次数上界：1 个维度 = 4 条 SQL（总量×2 + 下钻×2），K 个维度 =
  2 + 2K 条；系统提示词与工具描述中写明，防止 LLM 反复重跑

## 5. P3 RAG 混合检索

### 5.1 检索层

```
src/seatunnel_agent/text2sql/retrieval.py
  HybridRetriever
    - 文档粒度：每表一文档（表名+表注释+全部列名/列注释），每指标一文档
    - 通道 A（保底，零依赖）：BM25（纯 Python 实现，分词复用 matcher 的
      英文标识符 + CJK n-gram 切分）
    - 通道 B（可选）：向量检索——embedding 走 OpenAI 兼容 /embeddings
      端点（项目已是多 provider 架构，settings 加 embedding_model 一项）；
      未配置时自动降级为 A
    - 融合：score = w1·keyword(现有 matcher) + w2·bm25 + w3·vector，
      权重可在 .env 覆盖；默认 0.4/0.3/0.3（无向量时 0.55/0.45/0）
  索引持久化：logs/.t2s_index/<schema_hash>.json（DDL 内容哈希做键，
  schema 变更自动重建；向量缓存同键存 npy/json，避免重复计费）
```

### 5.2 接入点（两处，都是替换打分函数，不改调用协议）

1. `match_tables` 工具内部：matcher.rank → HybridRetriever.rank
2. `prompts.py` schema 摘要：表数 ≤ 阈值（默认 50）时全量注入（现状）；
   超过阈值时只注入检索 Top-K（默认 30）+ 一行"其余 N 张表可用
   match_tables 检索"——这是 context rot 的直接对策

### 5.3 评测（防止"升级反而变差"）

`tests/fixtures/t2s_retrieval_bench.jsonl`：≥50 条(问题, 期望表)标注对。
`seatunnel-agent t2s-bench` 输出 Top1/Top3 命中率，对比 keyword-only 与
hybrid 两种模式；CI 中作为回归门禁（hybrid 不得低于 keyword-only）。

## 6. P4 订阅推送

```
src/seatunnel_agent/text2sql/subscriptions.py
  SubscriptionStore     # JSON 文件存储，风格/上限对齐 favorites.py
  Subscription: id, name, favorite_id | metric+params, cron, ds/connection,
                webhook_url, lang, enabled, last_run, last_status
  Scheduler             # 后台线程，60s tick 扫描到期任务（croniter 解析），
                        # UI 启动时随 app 拉起；CLI `t2s-cron --once|--serve`
                        # 供无 UI 部署
  push_feishu(webhook, result, chart_png?) # 飞书卡片：标题 + 结果表格
                        # (≤10 行) + 环比标注 + 失败时错误摘要也推送
```

- 数据来源二选一：收藏的参数化 SQL（`favorites.py` 已支持 `${param}`，
  新增内置参数 `${yesterday}`/`${today}`/`${last_month}` 的求值）或
  P1 的指标+参数（走确定性端点，不消耗 LLM token）
- 安全：webhook URL 存 settings_store（已有加密基建）；执行仍走
  validator + 表白名单；连接复用"已保存连接"（settings 页已有）
- UI：/text2sql 页新增"订阅"标签页——列表（下次执行时间/上次状态）、
  新建表单、手动"立即执行"按钮

## 7. P5 Text2SQL MCP Server

`src/seatunnel_agent/text2sql/mcp_server.py`，完全照搬 skew/lineage 的
成熟范式（`build_tool_functions` 纯函数 + `create_mcp_server` 包装
FastMCP，无 mcp 包也可单测）。CLI：`seatunnel-agent t2s-mcp`。

| MCP 工具 | 说明 | 风险控制 |
|----------|------|----------|
| list_tables / get_table_schema | 只读元数据 | 无 |
| match_metrics / explain_metric | 指标目录与口径 | 无 |
| build_metric_sql | 确定性展开，只返回 SQL 不执行 | 无 |
| execute_readonly_sql | 执行 SELECT | 默认关闭，`--allow-execute` 显式开启；validator 全量校验；LIMIT 强制 |

不暴露"NL 直接到结果"的大工具——外部 agent 自己就是 LLM，MCP 只提供
确定性原子能力，避免 LLM 套 LLM 的成本与不可控。数据库连接从环境/已保存
连接读取，**不接受 MCP 参数传入密码**。

## 8. 数据安全（对齐文章红线）

- 指标查询与订阅全部经过既有 validator（SELECT-only、表白名单、LIMIT、
  分区过滤强制）
- MCP 执行默认关闭；开启后也只读
- 飞书卡片只推聚合结果（≤10 行），不推明细 CSV 内容，CSV 仅本地落盘
- qlog 扩展：`source` 字段（ui/api/mcp/subscription）+ `metric` 字段，
  审计谁在什么渠道查了什么指标

## 9. 测试计划

| 层 | 内容 |
|----|------|
| 单元 | metrics.yaml 解析/校验（坏配置逐条报错）、build_metric_sql 黄金文件（各方言×加法/比率×有无分区）、归因数学性质（贡献和≡总变动、新增/消失维度值）、BM25 排序、订阅 cron 到期判定（冻结时钟）、飞书卡片 payload |
| 集成 | sqlite fixture 走通 S1/S3 全链路（executor 已有 sqlite 后端）；REST 新端点；MCP 工具函数直调 |
| 检索评测 | 5.3 的 bench 作为回归门禁 |
| UI | 复用 ui_testing 框架新增用例：指标面板搜索/点击填充、订阅创建、归因报告渲染 |

## 10. 里程碑

| 里程碑 | 内容 | 验收 |
|--------|------|------|
| M1 | P1 语义层（metrics.py + 2 工具 + 提示词 + UI 面板 + CLI/REST） | S1/S2 场景演示；同一指标问题 10 次生成 SQL 逐字节一致 |
| M2 | P2 归因（attribution.py + 工具 + 瀑布图 + 报告） | S3 场景演示；贡献和自检恒等 |
| M3 | P3 RAG（retrieval.py + 两处接入 + bench） | 800 表 fixture 上 Top3 命中率 ≥ keyword-only；提示词长度封顶 |
| M4 | P4+P5（订阅 + MCP） | S5 飞书真实推送；Claude Code 注册 MCP 完成 S6 |

依赖关系：M2 依赖 M1（归因建立在指标之上）；M3/M4 与 M2 无依赖可并行。

## 11. 新增依赖

- `croniter`（订阅调度，轻量纯 Python）
- 其余零新增：YAML 解析用现有 pyyaml，BM25 纯手写（~60 行），
  embedding 复用 OpenAI 兼容 HTTP 调用，飞书推送用标准库 urllib/requests（项目已有 requests）
