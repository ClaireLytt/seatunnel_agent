# NEXT — 合入 PR #152 之后的地平线

本文件固化 pso 分支收官时的候选盘点：哪些值得做、各自等什么闸门、
哪些查重后决定不做。避免结论只活在对话里。

## 等「合入 + 新基线」

- **room1913 英文开关** — 全站文案的 中/EN 切换。触及所有页面与内容库
  （对谈脚本、测验题、种子文案），独立 PR 体量；基础设施建议
  localStorage + 挂载后切换（避免 hydration 不一致，教训见
  docs/reports 的 hydration 修复记录）。
- **room1913 KV 多人验证** — `room1913/app/lib/store.ts` 的 KV 驱动
  已就绪，部署配好 `KV_REST_API_URL/TOKEN` 后做真实多访客的
  交换/点灯/回信/在场验证；随后按 room1913/ROADMAP.md 处理
  交换轮转与限频。
- **room1913 年册** — 需要跨月真实数据才有意义，刻意推迟。

## 待做（无闸门,下一轮候选）

- **治理总览页 /governance** — 聚合 logs/*.jsonl 趋势(孤儿表、注释
  覆盖、违约数、权限面)。前置:给 contract/grants/ddlguard 补
  RunLogger(seam 现成)+ stats REST 端点;体量一个完整页面。

## 等「有效 ANTHROPIC_API_KEY」

- **room1913 对话验收** — 唯一未端到端验证的功能（客户端链路与错误
  兜底已验，上游 401 待解）。
- **园丁周记 / 圆桌引用记录 / 五问追问** — 见 room1913/ROADMAP.md。
- **本仓库 LLM 增强面** — 如 pii 报告的 LLM 列描述（与 datadict 的
  可选 LLM 描述同模式），确定性核心不变。

## 查重后决定不做（附理由）

- **`/costlint` 成本静态体检** — sql_review 已完整覆盖
  （join_cartesian / partition_pruning / resource_usage /
  where_partition），再做即重复造轮子。
- **日志类新 agent** — log_inspect + advisor + ciinspect 已满。
- **数据对比扩展** — data_comparison 完整；且属独立 ccmetr 任务 (#20)。
- **hygiene 的"无前缀表"命名告警** — 实测对每张表报噪音，规则
  收紧为只报跨层错配；不要回退。
- **小文件/compaction 体检、表热度画像** — 需要运行时元数据
  （HDFS 列表、查询日志），静态 SQL 看不见；不做静态猜测版。
- **SeaTunnel 配置升级助手** — config_migrate 已存在。
- **样本数据脱敏预览** — sql_testgen × pii_mask 组合已覆盖。
- **hub widget host（首页挂件宿主 seam）** — 2026-10-29 架构评审
  候选 4：目前只有 garden 一个首页挂件，单 adapter = 假想 seam；
  等第二个挂件真实出现再抽象，先按内联实现维护。

## 其他 ccmetr 任务（另开 session 领取）

#6 text2sql、#9 sql review、#20 data comparison、#21 data skew、
#22 ui test agent、#35 chat bi — 均为独立任务，不应在本分支混做。
