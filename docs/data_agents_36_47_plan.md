# 数据工程 Agent 36–47 实施计划

延续 25–35 的平台插件模式（manifest 自动发现：hub 卡片 + REST + MCP 工具 +
React 页 + CLI），骨架与质量基线不变：确定性核心、zh/en 报告、示例、
单测 + 页面回归、gate 全 PASS。复用既有公共设施：
`common.api_factory.make_text_router`（候选 1 新落地，文本形输入一律走它）、
`api_guard.read_whitelisted_file`、check_runner 的 emit/gate/history、
advisor_llm 模式、`frontend/shared` 的 useRunner/handoff、extra_routers
双页测试、data_skew 门面（跨包只 import 包级名字）。

## 查重结论（先于开发）

- **36 分布异常 vs data_quality**：data_quality 是规则驱动的阈值体检
  （row_count/null_rate/unique/enum）；36 做的是**无规则的分布漂移对比**
  （两份剖面快照：均值/分位数/类别占比的显著变化）。互补，不合并。
- **37 重复检测 vs data_quality.unique**：unique 只报违规计数；37 输出
  重复**明细定位**（重复组、首末出现、疑似来源字段组合）。独立。
- **38 根因追踪 vs data_lineage**：复用 data_lineage 的解析器做上游行走，
  38 只新增"质量事件 × 血缘"的叠加判定，不重写血缘。
- **39 波动分析 vs data_freshness**：freshness 管"有没有按时来"；39 管
  "来的量/值对不对"（环比/同比/移动中位数的突变）。独立。
- **40 一致性修复**：消费 36/37 形状的发现，生成修复 SQL 方案——是
  37 的下游，排在其后实现。
- **41 抽样分析**：输入即数据行（CSV/JSONL），纯剖面；36 的剖面构造器
  从 41 的 profiler 复用（41 先行）。
- **44 价值评估 / 45 存储成本**：同一份"资产清单"输入风格（访问频次、
  大小、依赖数），45 偏清理动作、44 偏分级定性；共用清单解析器。
- **47 权限审核 vs grant_scan**：grant_scan 审"已授出的面"；47 审
  "申请单的风险"（角色 × 用途 × 字段敏感级，复用 pii_scan 的敏感级
  词表思路）。互补。
- **46 数据库运行诊断 vs mcp_toolbox**：46 为文本形输入（状态快照/
  processlist/锁等待清单），不连库也能诊断；连库实测留给 mcp_toolbox
  已有通道。

## 套件一：质量异常（36–41，group quality）

- **41 数据抽样分析 — `sample_profile`**（route `/sampleprofile`）先行：
  输入 CSV/JSONL 行 + 可选列类型提示；分层/均匀抽样 → 每列剖面
  （类型推断、空值率、唯一率、min/max/均值/分位、top 类别、格式聚类
  如日期/电话/邮箱的 regex 桶），异常字段清单（混合类型、离群格式）。
- **36 数据分布异常检测 — `dist_anomaly`**（route `/distanomaly`）：
  输入基线剖面 × 当前剖面（或两份原始样本，内部用 41 的 profiler）；
  判定均值/分位漂移（相对阈值）、类别占比变化（L1 距离 + 新增/消失
  类别）、空值率/唯一率突变；输出按严重度排序的漂移卡。
- **37 数据重复检测 — `dup_check`**（route `/dupcheck`）：输入数据行 ×
  可选主键/业务键声明；全行重复、主键重复、业务事件重复（键组合）
  三层检测；每组给出现次数、首末行号、差异列（定位来源）。
- **39 数据波动分析 — `data_volatility`**（route `/datavolatility`）：
  输入指标时间序列（jsonl/CSV：date,metric,value，复用 trends 风格）；
  移动中位数 + MAD 判surge/drop、周期对比（环比/同比）、断点清单；
  输出波动卡 + 处方（指向 38 根因追踪）。
- **38 数据质量根因追踪 — `quality_trace`**（route `/qualitytrace`）：
  输入质量事件（表+列+症状）× SQL 血缘树（data_lineage 解析）；
  沿上游行走为每个祖先打嫌疑分（距离、列级命中、JOIN/过滤改动点）；
  输出嫌疑排行榜 + 验证 SQL 建议。
- **40 数据一致性修复 — `data_repair`**（route `/datarepair`）：输入
  37/36 形状的发现（或原始行自检）；生成确定性修复方案：去重 SQL
  （ROW_NUMBER 保留策略）、空值回填策略（默认值/前向/上游重跑）、
  格式标准化（日期/大小写/trim）CASE/UPDATE 片段；LLM 可选润色说明。

## 套件二：资产治理（42–47，group governance）

- **42 数据资产搜索 — `asset_search`**（route `/assetsearch`）：输入
  资产目录（DDL 集合或 JSON 清单：表/字段/注释）× 自然语言查询；
  确定性检索：分词 + 同义词表 + 字段注释/名称加权打分；LLM 可选
  重排与解释。
- **43 数据字典自动生成 — `data_dict`**（route `/datadict`）：输入 DDL
  ± SQL 使用集；确定性骨架：类型/约束/血缘推字段角色（维度/度量/键），
  使用频次注入；LLM 补业务描述（逐字段，缺 LLM 时输出骨架字典）。
- **44 数据资产价值评估 — `asset_value`**（route `/assetvalue`）：输入
  资产清单（访问次数、最近访问、下游依赖数、大小）；分级打分
  （核心/常用/边缘/闲置）+ 四象限（价值 × 成本）清单。
- **45 存储成本治理 — `storage_cost`**（route `/storagecost`）：同款
  清单 + 分区明细；识别长期未访问大表、过期分区、碎片小文件表；
  输出动作清单（冷备/清理/合并）与预计释放量；复用 44 的清单解析。
- **46 数据库运行诊断 — `db_diag`**（route `/dbdiag`）：输入状态快照
  文本/JSON（连接数、Threads_running、锁等待、死锁日志、慢查询条目、
  QPS/负载）；规则判定：连接池耗尽、锁风暴、死锁环、慢查询热点；
  输出诊断卡 + 处方（指向 slow_query/index_advisor）。
- **47 数据权限申请审核 — `grant_review`**（route `/grantreview`）：
  输入申请单（人/角色/库表字段/用途/期限）× 敏感级规则（复用
  pii_scan 词表思路）；风险评分（敏感级 × 范围 × 期限 × 角色匹配度），
  给出 批准/降级批准/拒绝 建议与依据。

## 实施顺序与里程碑

1. [ ] 41 sample_profile（profiler 是 36/40 的地基）
2. [ ] 36 dist_anomaly（复用 41 profiler）
3. [ ] 37 dup_check
4. [ ] 39 data_volatility
5. [ ] 38 quality_trace（复用 data_lineage）
6. [ ] 40 data_repair（消费 36/37 发现，套件一收口）
7. [ ] 42 asset_search
8. [ ] 43 data_dict
9. [ ] 44 asset_value（清单解析器）
10. [ ] 45 storage_cost（复用 44 解析）
11. [ ] 46 db_diag
12. [ ] 47 grant_review（套件二收口）

每个 agent 独立提交：后端（core/report/i18n/api[make_text_router]/tools/
manifest/cli）+ 测试 + 示例 + 前端页（useRunner）+ 页面回归 + 报告落盘；
节奏沿 25–35 的 phase 模式，后续允许每个 agent 继续叠加增强。
