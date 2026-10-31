# 数据工程 Agent 48–52 实施计划（实时链路套件）

延续 36–47 的平台插件模式（manifest 自动发现：hub 卡片 + REST
[make_text_router] + MCP 工具 + React 页 [useRunner] + CLI），骨架与
质量基线不变：确定性核心、zh/en 报告、示例、单测 + 页面回归、gate 全
PASS。文本/快照输入，不连 Kafka/Flink/数据库。

## 查重结论（先于开发）

- **48 vs slow_query**：slow_query 管批作业单次运行指标；48 管 Kafka
  消费组 lag 快照（分区粒度、追赶 ETA）。独立。
- **49 vs data_skew runtime**：skew-runtime 管 Spark/Flink 的 task 级
  倾斜；49 管 Flink 作业健康面（checkpoint/背压/watermark/重启），
  互补，处方互指。
- **50 vs data_freshness / sla_trace**：freshness 管批表"有没有按时
  来"、sla_trace 管调度关键路径；50 管事件级端到端延迟（生产→摄入→
  计算→落地各段分位）。独立。
- **51 CDC 诊断**：binlog/offset/断点/丢数均无现有覆盖。新建。
- **52 vs data_comparison / metric_diff**：data_comparison 是连库
  checksum/分块比对，metric_diff 管 SQL 口径定义；52 做**文本形双侧
  结果集核对**（粘贴实时与离线两份结果，按键对齐 + 容差 + 系统性偏差
  判定），复用 sample_profile.parse_rows。互补。

## 套件三：实时链路（48–52，group quality）

- **48 Kafka 消费积压 — `kafka_lag`**（route `/kafkalag`，order 75）：
  输入消费组快照（JSON：topics[].partitions[] 的 log_end_offset/
  committed_offset/consume_rate/produce_rate，或同字段 CSV）。
  规则：总积压量级、单分区热点（max/median lag）、消费速率 < 生产
  速率（永不追上 vs 追赶 ETA = lag/(consume-produce)）、停滞分区
  （速率 0 且有 lag）。
- **49 Flink 作业诊断 — `flink_diag`**（route `/flinkdiag`，order 76）：
  输入作业快照（checkpoints[]、operators[] 的 backpressure/busy、
  watermark_lag_ms、restarts）。规则：checkpoint 失败/超时、时长
  爬升趋势、对齐耗时占比高（建议 unaligned）、背压算子（0.5/0.8）、
  watermark 滞后、频繁重启；处方指向 skew-runtime/kafkalag。
- **50 实时延迟分析 — `rt_latency`**（route `/rtlatency`，order 77）：
  输入事件时间戳行（CSV/JSONL：event_id,produce_ts,ingest_ts,
  process_ts,sink_ts，段可缺省）。输出各段与端到端的 p50/p95/max、
  主导段判定、离群事件（> p95×3 附 event_id）、给定阈值的破线率。
- **51 CDC 同步异常 — `cdc_diag`**（route `/cdcdiag`，order 78）：
  输入同步快照（source 端 binlog file/position/retention_hours、
  consumer 端 file/position/last_event_ts、可选 errors[] 与表级
  offsets[]）。规则：binlog 文件落后、position 差距、事件停滞、
  保留期风险（追不完 binlog 就被清 → 丢数风险）、错误模式归类
  （schema 变更/主键冲突/连接）、consumer 超前 source（断点错乱）。
- **52 实时离线核对 — `rt_offline_diff`**（route `/rtoffline`，
  order 79）：输入两份结果集（CSV/JSONL）+ 键列 + 容差%。按键对齐：
  双侧缺失键、超容差的指标差异（附行）、系统性偏差判定（实时普遍
  偏低 → 迟到数据/窗口未闭合；普遍偏高 → 重复消费），汇总一致率。

## 实施顺序与里程碑

1. [x] 48 kafka_lag
2. [x] 49 flink_diag（处方指向 48 与 skew-runtime）
3. [x] 50 rt_latency
4. [x] 51 cdc_diag
5. [x] 52 rt_offline_diff（复用 sample_profile 行解析，套件收口）

每个 agent 独立提交：后端 + 测试 + 示例 + 前端页 + 页面回归 + 报告落盘。
CLI 统一挂在 cli_cmds/quality_ops.py（与 36–47 同一注册面）。
